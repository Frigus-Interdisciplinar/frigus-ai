# LangChain / LangGraph

## Usar `response_format` em vez de parsear texto livre com regex — `agents/nodes/router.py` está no antipadrão hoje

Se um nó espera uma decisão estruturada do LLM (rota, categoria, campo extraído), não peça pro
prompt devolver um formato tipo `ROUTE=financeiro` e depois cace isso com regex na resposta — o
LLM pode variar o formato e o regex silenciosamente cai no fallback errado. `create_agent` aceita
um `response_format` (Pydantic model) e já resolve isso dentro do próprio loop do agente (via
tool-calling ou structured output nativo do provider, sem chamada extra de LLM), devolvendo o
resultado tipado em `result["structured_response"]`.

**Aqui:** `agents/nodes/router.py:no_roteador` faz exatamente o `DO NOT DO THIS` abaixo hoje —
`re.search(r"ROUTE=(\w+)", texto)` sobre `router_app.invoke(...)["messages"][-1].content`. Não é uma
pegadinha teórica, é o código atual. Migrar quando mexer nesse nó de novo.

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

saida = router_app.invoke({"messages": list(estado["messages"])})
roteamento = saida["structured_response"]  # já é um Roteamento, sem parsing manual
```

Instead of (estado atual de `agents/nodes/router.py`):

```python
# DO NOT DO THIS
saida = router_app.invoke({"messages": list(estado["messages"])})
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
    agentes_chamados: Annotated[list[str], operator.add]
```

Instead of:

```python
# DO NOT DO THIS
class Estado(MessagesState):
    agentes_chamados: list[str]  # cada nó que retorna isso PISA no valor anterior, não acumula
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
saida = financeiro_app.invoke({"messages": mensagens})
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
