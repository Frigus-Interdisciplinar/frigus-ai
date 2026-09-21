# Contratos do grafo, repositories SQLAlchemy e guardrail

Sessão em `refactor/structure`. Suíte ao fim: **177 passed**, ruff limpo.
Ponto de partida: `graph/builder.py` estava com **erro de sintaxe** (corpo de
`_construir_grafo()` sem indentação, `grafo` vazando no módulo) — o módulo não importava.

## Feito

### Contratos tipados do grafo

- `graph/state.py`: `AsyncNode[R]`, `EntradaGrafo`/`SaidaGrafo` e um `*Update` por nó
  (`EspecialistaUpdate`, `FaqUpdate`, `RouterUpdate`, `OrquestradorUpdate`, `JuizUpdate`,
  `GuardrailEntradaUpdate`, `GuardrailSaidaUpdate`). Campos do `Estado` viraram `NotRequired`.
- `graph/builder.py` reescrito no padrão que estava comentado embaixo dele, com
  `input_schema=EntradaGrafo, output_schema=SaidaGrafo`. Bloco comentado removido.
- Nós devolvem o TypedDict e usam `HumanMessage`/`AIMessage`/`SystemMessage`. Não sobrou
  nenhum `{"role": ...}` solto.
- `services/runner.py`: `_estado_inicial` agora devolve só o que `EntradaGrafo` aceita.

### `names.py` saiu de `nodes/` (divergência deliberada do assessor)

`state.py` precisa de `NodeLiteral`; importar de dentro do pacote `nodes` executava
`nodes/__init__.py` → todos os nós → `state` de novo. `import frigus_ai.graph.state`
sozinho morria com ImportError. **O assessor tem o mesmo ciclo latente**, só não estoura
porque lá o `builder` sempre importa `nodes` primeiro. Movido para `graph/names.py`.

### Helpers de nó (`graph/nodes/contexto.py`)

- `responder(app, mensagens)` — agente compilado (`{"messages": [...]}`).
- `perguntar(llm, entrada)` — LLM cru (devolve uma `AIMessage` só). Os dois validam que o
  conteúdo é texto; antes ninguém checava e resposta multimodal vazaria como lista de blocos.
- `mensagens_do_turno(...)` — absorveu o append do feedback do Juiz, que estava copiado em 5 nós.
- `podar_historico(...)` — ver abaixo.

### Poda do histórico (o "grafo pesado" não era o grafo)

Medido: grafo compilado = **112 KiB**; os imports (langchain/langgraph/sqlalchemy/agentes) =
**153 MiB**. O cache do `FluxoAgentes` é irrelevante em memória e o lock não pesa (o fast path
retorna antes de adquirir). O que crescia era o canal `messages`: **3 msgs por turno, sem teto**
(40 turnos = 120 msgs), e todo turno relia tudo pro contexto do LLM — custo em token, não só RAM.
`podar_historico` emite `RemoveMessage` no nó de entrada; estabiliza em 23 msgs.
Cortar por contagem só é seguro porque o canal guarda apenas Human/AI de texto (as tools rodam
no sub-grafo de cada agente). **Se um `ToolMessage` entrar no estado, isso quebra.**

### Repositories: `financeiro` e `estoque` saíram do SQL cru

Padrão do `receitas`: repository faz persistência, tool faz `Response`/log/negócio.
- `financeiro`: só leitura. `gastos_por_mes` resolve N meses em **uma** query (antes uma por mês)
  e devolve `0.0` para mês sem movimento, que antes sumia do dict e causaria `KeyError` na
  `comparacao_mensal`.
- `estoque`: primeiro com escrita. Cada método público é uma unidade de trabalho sob
  `@transacional`, com localizar + alterar na MESMA transação. Upsert virou
  `insert(...).on_conflict_do_update(...)`; SQL gerado conferido contra o original.
  Regras viraram exceptions de domínio (`ItemDeEstoqueNaoEncontrado`, `QuantidadeNegativa`).
  `_localizar` passou a prender o `stock_id` também no caminho por ID (antes um ID de outro
  estoque era alcançável).

**Armadilha:** `estoque.descartar()` grava a saída em `stock_movements` com a MESMA data do
`discard`; é por `(stock_product_id, date)` que o `financeiro_repository` casa os dois pra
calcular desperdício. Mudou a data, o valor desperdiçado vira zero em silêncio. Tem teste.

### `privacy.py` e reorganização do guardrail

- `chat_repository` e `user_service` importavam `anonimizar_entrada` **de dentro de um nó do
  LangGraph** — persistência dependendo do grafo. PII foi para `frigus_ai/privacy.py`
  (neutro, espelha `assessor_ai/privacy.py`, cuja docstring descreve o mesmo problema).
  Hoje nada fora de `graph/` importa `graph/nodes/`.
- `guardrail/` saiu de `graph/nodes/` para **`graph/guardrail/`** (movido pelo usuário):
  `padroes.py` (ataque), `schemas.py` (tipos + política), `cache.py` (Redis), `entrada.py`/
  `saida.py` (só os nós). Testes em `tests/graph/guardrail/`.
- `RESPOSTAS_BLOQUEIO` virou `dict[Categoria, RespostaBloqueio]` e `Motivo` virou `Literal`
  (é label do Prometheus — typo criaria série nova).
- Cache do classificador no Redis: chave carrega fingerprint do prompt (editar `guardrail.md`
  invalida sozinho) e normaliza tokens de PII antes do hash (o token tem sufixo aleatório,
  senão mensagem com PII nunca bateria).

### Correções de segurança/robustez achadas no caminho

- **`POST /chats/{id}/messages/stream` não checava ownership**, enquanto o gêmeo não-streaming
  checava. O checkpointer indexa por `thread_id=session_id` sem `user_id`, então o chat_id de
  outro dono carregava a conversa dele no contexto do LLM e voltava pelo SSE. O Mongo é
  escopado por dono, o checkpoint não era. A checagem teve que ir para **dependência**, não
  para o corpo da rota: o corpo de um gerador só roda depois que o status HTTP saiu.
- **Redis sem timeout** custava ~4s por chamada com o serviço fora do ar (retry do redis-py,
  medido). `socket_connect_timeout`/`socket_timeout` de 0.5s — vale pra rate limit e perfil
  também. O cache do guardrail ainda se desliga por 30s após falha.
- **`Categoria("SPAM")`** estourava `ValueError` se o LLM inventasse categoria, derrubando o
  turno em vez da falha aberta. Lookup voltou a ser por `str`.

## Cuidados para a próxima sessão

- `MAX_MENSAGENS = 21` em `graph/nodes/contexto.py` é o teto do checkpoint. Revisar se algum
  nó passar a publicar `ToolMessage` no estado.
- `compras` é o último domínio em SQL cru (5 `get_conn`). `health.py` mantém o ping cru de
  propósito.
- `E402` não está no ruleset do ruff do projeto — foi assim que um import no meio do
  `entrada.py` passou pela CI.
