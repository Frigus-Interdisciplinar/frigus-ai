# LangChain / LangGraph

## Usar `response_format` em vez de parsear texto livre com regex — já é assim em `graph/nodes/router.py`

Se um nó espera uma decisão estruturada do LLM (rota, categoria, campo extraído), não peça pro
prompt devolver um formato tipo `ROUTE=financeiro` e depois cace isso com regex na resposta — o
LLM pode variar o formato e o regex silenciosamente cai no fallback errado. `create_agent` aceita
um `response_format` (Pydantic model) e já resolve isso dentro do próprio loop do agente (via
tool-calling ou structured output nativo do provider, sem chamada extra de LLM), devolvendo o
resultado tipado em `result["structured_response"]`.

**Aqui:** `graph/nodes/router.py:no_roteador` fazia exatamente o `DO NOT DO THIS` abaixo
(`re.search(r"ROUTE=(\w+)", texto)`) — migrado: `router_app` usa `response_format=Roteamento`
(`graph/state.py`), e o guardrail de entrada usa `with_structured_output(Classificacao)` pelo
mesmo motivo. Falha do LLM vira `fim` com resposta genérica, sem derrubar o turno.

Do this:

```python
from pydantic import BaseModel
from langchain.agents import create_agent


class Roteamento(BaseModel):
    rota: Route
    pergunta_original: str


router_app = create_agent(
    model=llm_rapido,
    system_prompt=RouterPrompts.system_prompt(),
    response_format=Roteamento,
)

saida = await router_app.ainvoke({"messages": list(estado["messages"])})
roteamento = saida["structured_response"]  # já é um Roteamento, sem parsing manual
```

Instead of (como o roteador era antes):

```python
# DO NOT DO THIS
saida = await router_app.ainvoke({"messages": list(estado["messages"])})
texto = saida["messages"][-1].content
match = re.search(r"ROUTE=(\w+)", texto)  # quebra se o LLM variar o formato
rota = Route(match.group(1)) if match else Route.FIM
```

## Reducer explícito em toda lista/dict acumulado no `State` — já é assim em `graph/state.py`

Campo de `State` do LangGraph sem `Annotated[..., reducer]` é sobrescrito a cada nó que retorna
essa chave, não mesclado — o padrão do LangGraph é "last write wins". Listas que crescem entre nós
(histórico, agentes chamados) precisam de reducer explícito (`operator.add`, ou `add_messages` pra
mensagens, que também deduplica por id e faz merge de chunks). `Estado` em `graph/state.py` já faz
isso certo:

```python
import operator
from typing import Annotated

from langgraph.graph import MessagesState


class Estado(MessagesState):  # messages já vem com add_messages embutido
    dados_especialistas: Annotated[list[ResultadoEspecialista], operator.add]
```

Instead of:

```python
# DO NOT DO THIS
class Estado(MessagesState):
    dados_especialistas: list[ResultadoEspecialista]  # cada nó que retorna isso PISA no valor anterior, não acumula
```

Ao adicionar campo novo que acumula entre nós, use o mesmo `Annotated[..., operator.add]`.

## `system_prompt` de `create_agent` congela no import — contexto dinâmico vai por mensagem

`create_agent(..., system_prompt=X.system_prompt())` avalia a string **uma vez**, quando o módulo é
importado (`graph/agents.py`, que constrói `router_app`, `estoque_app`, `compras_app`,
`receitas_app`, `faq_app`, `financeiro_app`, `orquestrador_app` assim). Qualquer coisa que mude com
o tempo embutida ali fica congelada pelo tempo de vida do processo: data/hora, perfil do usuário,
contexto do turno. No terminal passa despercebido porque reinicia a cada uso — uma API rodando dias
não. Sem incidente confirmado aqui ainda (nenhum prompt atual embute algo dinâmico), mas o padrão é
o mesmo do assessor-ai, onde isso já aconteceu de verdade (bloco de data interpretado como a data do
deploy, não a de agora).

Do this — o que muda por turno entra como mensagem de sistema no `invoke`, não no `system_prompt`:

```python
mensagens = [{"role": "system", "content": contexto_do_turno(perfil, pergunta)}, *estado["messages"]]
saida = await financeiro_app.ainvoke({"messages": mensagens})
```

Instead of:

```python
# DO NOT DO THIS — a data é a do import, não a de agora
class GenericAgent:
    CONTEXTO_TEMPORAL = f"Data atual: {datetime.now()}"   # roda uma vez, no import do módulo
```

**Ressalva sobre providers (Gemini/Groq, os dois usados aqui):** duas system messages na mesma lista
funcionam nos dois — Groq é OpenAI-compatible e aceita várias; o `langchain-google-genai` **funde**
as system messages extras no mesmo `system_instruction` (verificado em `_parse_chat_history` — vira
uma segunda `part`, não um erro), mas só se já houver uma system message no índice 0 — se não houver,
o `langchain-google-genai` **descarta a segunda em silêncio**, sem erro nem warning. Hoje é seguro
porque todo agente aqui é criado com `system_prompt`, que o `create_agent` prepende. Agente sem
`system_prompt` + contexto por mensagem = contexto perdido sem aviso.

Alternativa mais formal, se um dia precisar do prompt inteiro dinâmico: o middleware
`dynamic_prompt` do `langchain.agents.middleware`, que recalcula o system prompt a cada chamada de
modelo.

## Nó de grafo `async def` não exige que as tools também sejam async

A migração pra async converteu os nós de `graph/nodes/` pra `async def` +
`.ainvoke()` (no `*_app` de `graph/agents.py` e nos `llm_*.invoke` diretos de `juiz.py`/
`guardrail/*.py`). As tools chamadas pelos agentes (`ESTOQUE_TOOLS` etc., psycopg2/pymongo por
baixo) **continuam `def` sync sem nenhuma mudança** — `create_agent`/`ToolNode` do LangChain já faz
offload automático pra thread quando a tool é sync e o agente roda via `.ainvoke()`, propagando
`contextvars` corretamente (`infra/postgres/context.py:session_context`) sem precisar de
`asyncio.to_thread` explícito nesse nível. Só vale reescrever uma tool pra `async def` se ela mesma
ganhar um client async de verdade (ex. Redis/Qdrant) — nada obrigatório aqui.

## Timeout e retries dos LLMs: o default é "esperar pra sempre"

Nenhuma classe (`ChatGoogleGenerativeAI`, `ChatGroq`, `ChatOpenAI`) vem com timeout, e o
`max_retries` do Gemini tem default **6**. Medido contra um 503 lento: sem timeout a chamada dura
o tempo que o servidor quiser (o 503 "high demand" real leva 9-17s), 3 tentativas = 12s, e um
`timeout` de 1s derruba a tentativa em 1,0s. Hoje isso vem da política por provider em
`settings/llm.py` (`LLM__GEMINI__TIMEOUT_S`, `LLM__GEMINI__RETRIES`, ...), aplicada em
`infra/llm/builder.py`. Armadilhas:

- `max_retries` NÃO significa a mesma coisa em todo provider: no Gemini são tentativas **totais**
  (1 = sem retry); em Groq/OpenAI/Anthropic são as **extras**. A política usa sempre "extras" e o
  builder converte.
- `timeout` é por tentativa, em segundos (o wrapper do Gemini converte pra ms). Pior caso de um
  provider caído = `(retries + 1) * timeout`.
- Sobrescrever uma chave de `dict` por env SUBSTITUI o dict inteiro e os outros itens somem
  (`KeyError`). Por isso cada provider é um submodelo de `LLMSettings` (`LLM__GROQ__RETRIES=2`
  mexe só nesse campo), não um dict.
- Groq no plano gratuito tem TPM de 8000 tokens/min pro gpt-oss-120b: uma rajada de turnos dá 429
  e, no roteador (sem fallback, `llm_rapido`), vira "Não consegui entender o pedido".
- Cota **diária** do Gemini (429 `PerDayPerProjectPerModel`) falha em ~0,4s e só volta no dia
  seguinte; já o 503 de capacidade é que demora.

## `with_fallbacks` esconde o `with_structured_output`

`model.with_fallbacks([...])` devolve um `RunnableWithFallbacks`, que NÃO tem `with_structured_output`:
chame `with_structured_output` em cada modelo e só depois monte a cadeia (`graph/llm.py:estruturado`).
Isso importa porque um papel com um provider só (guardrail, juiz) falha aberta e aprova tudo quando
ele cai. `create_agent` aceita a cadeia direto (`com_reserva`). Groq usa `method="json_schema"`;
`gpt-5*` descarta `temperature` ≠ 1 sozinho (a lib remove).

## O Juiz precisa do retorno das tools, não do texto do agente

`agente.ainvoke(...)` devolve `{"messages": [...]}` com todas as mensagens do passo a passo: as
`ToolMessage` são o que as tools retornaram. Se o Juiz compara a resposta com o texto final do
próprio agente, ele compara a resposta com ela mesma e nunca pega alucinação.
`graph/nodes/contexto.py:responder_com_evidencias` separa as duas coisas: devolve o texto final e
as `ToolMessage` juntas (`name:
conteúdo`, vazio se o agente não chamou tool). Isso só vale porque
`messages` do estado guarda apenas Human/AI de texto, então toda `ToolMessage` na saída é do turno.
Sem tool chamada, `dados` cai na própria resposta (não há o que conferir além dela).
