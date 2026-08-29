<div align="center">

# Frigus.AI

Assistente multi-agente do app **Frigus** — gestão de alimentos, receitas, compras e finanças domésticas.
Construído com LangChain + LangGraph, RAG (Qdrant), guardrails e um agente juiz (LLM-as-judge).

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat&logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.2-1C3C3C?style=flat&logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.1-FF6B35?style=flat)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-psycopg2-336791?style=flat&logo=postgresql&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-pymongo-47A248?style=flat&logo=mongodb&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-pyredis-DC382D?style=flat&logo=redis&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-Graph_Database-4581C3?style=flat&logo=neo4j&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector_Database-DC244C?style=flat&logo=qdrant&logoColor=white)


</div>

---

## O que o Frigus.AI faz

O Frigus.AI é o assistente conversacional do aplicativo Frigus (gestão de alimentos em geladeira, freezer e
despensa). Ele atua em cinco domínios:

**Estoque** — cadastra, consulta e atualiza itens do estoque; calcula o semáforo de validade
(Fresco / Próximo do vencimento / Vencido); registra descarte de itens vencidos.

**Compras** — gerencia a lista de compras, gera sugestões automáticas a partir de itens em baixa
(`minimal_quantity`) e tem um ponto de extensão para registrar compras via QR Code de NF-e.

**Receitas** — sugere receitas cruzando o estoque real do usuário com o banco de receitas (relacional).

**Financeiro (MoneySaving)** — gastos mensais, comparação entre meses, valor estimado de alimentos
descartados e evolução do desperdício ao longo do tempo.

**FAQ** — dúvidas sobre o funcionamento do app Frigus, via RAG (Qdrant) sobre `data/pdf/Frigus-Documentacao.pdf`.

Para tudo fora desses domínios (small talk, perguntas fora de escopo), o próprio roteador responde
diretamente ao usuário.

---

## Grafo de agentes

<div align="center">
  <img src="assets/diagrama-agentes.png" alt="Diagrama do fluxo de agentes do Frigus.AI" width="720" />
</div>

O **Juiz** é um agente LLM-as-judge: audita a resposta quanto a grounding (só usa dados que vieram das
tools), relevância e completude, ANTES do guardrail de saída. Se reprovar, a resposta volta para o mesmo
especialista que a gerou (com o motivo da reprovação), até 2 tentativas — depois disso, segue mesmo
reprovado (loga um aviso), para nunca travar o usuário.

---

## Estrutura do projeto

```
frigus-ai/
├── main.py                          # Dispatcher — `python main.py <interface>`
├── pyproject.toml
├── docker-compose.yml               # Postgres + Mongo + Redis + Qdrant
│
├── interfaces/tui/                  # app.py (Textual) + display.py (Bubble/MessageRow) + app.tcss
├── interfaces/api/                  # main.py (FastAPI) + auth.py (X-API-Key) + routes/{chats,health,keys,a2a}.py + schemas/
├── interfaces/mcp/                  # server.py — as tools de domínio como servidor MCP, montado em /mcp
├── config/                          # settings, models (LLM), logging, docker (compose up/down)
├── data/
│   ├── pdf/Frigus-Documentacao.pdf
│   └── sql/schema.sql               # DDL fornecido (schema `dataload`, 20 tabelas + 9 enums)
│
└── src/frigus_ai/                   # Pacote instalável com o "cérebro" do assistente
    │
    ├── chat/                        # Camada de serviço — usada por toda interface
    │   ├── models.py                # ChatMessage/Role — contrato próprio, independente do Mongo
    │   ├── repositories.py          # Acesso a tools/mongo/{chats,users}
    │   ├── runner.py                # Invoca o grafo (executar/executar_stream) e extrai a resposta
    │   └── service.py               # send_message, stream_message, get_history, iniciar/encerrar_sessao
    │
    ├── agents/
    │   ├── prompts/                 # Só .md + loader.py — nenhum outro .py na pasta
    │   │   ├── loader.py            # load_prompt()/load_sections(): frontmatter `---` (metadados,
    │   │   │                        # hoje só usa_tools_obrigatorias) + seções `## NOME` do .md
    │   │   ├── router.md / estoque.md / compras.md / receitas.md / faq.md / financeiro.md
    │   │   ├── orquestrador.md
    │   │   ├── juiz.md              # PAPEL + SHOTS + TEMPLATE (usado à parte, sem passar por load_prompt)
    │   │   ├── guardrail.md         # CLASSIFICADOR + COMPLIANCE (sem persona — load_sections cru)
    │   │   └── resumidor.md / perfil.md
    │   └── nodes/                   # Funções de nó do grafo LangGraph
    │       ├── names.py
    │       ├── router.py / estoque.py / compras.py / receitas.py / faq.py / financeiro.py / orquestrador.py
    │       ├── juiz.py
    │       └── guardrail/{entrada,saida,schemas}.py
    │
    ├── graph/
    │   ├── state.py                 # Estado e Route (Literal + classe de constantes)
    │   ├── llm.py                   # build_llm e instâncias de LLM
    │   ├── agents.py                # Agentes compilados (create_agent por especialista)
    │   └── builder.py               # Grafo (ciclo de retentativa do Juiz) + checkpointer Mongo
    │
    └── tools/
        ├── postgres/
        │   ├── connection.py        # Pool psycopg2 com search_path=dataload
        │   ├── context.py           # contextvars: current_user_id / current_stock_id
        │   ├── helpers.py           # resolve_stock_id, next_id, normalize_enum, semáforo
        │   ├── estoque/{schemas,core}.py
        │   ├── compras/{schemas,core}.py
        │   ├── receitas/{schemas,core}.py
        │   └── financeiro/{schemas,core}.py
        ├── mongo/                   # agent_chats + user_profiles + checkpoints do grafo
        ├── redis/                   # cache de perfil (perfil.py) + rate limit (chat.py) + API keys (api_key.py)
        ├── qdrant/faq/              # RAG (Qdrant) sobre Frigus-Documentacao.pdf — connection/core/ingest
        └── spoonacular/             # client HTTP (httpx) da Spoonacular Food API — receitas externas
```

`mcp_server/` e `a2a_server/` (placeholders vazios) deram lugar a `interfaces/mcp/` e à rota do
Agent Card em `interfaces/api/routes/a2a.py` — ver "MCP e A2A" abaixo.

---

## Persistência

| Camada | Tecnologia | Responsabilidade |
|---|---|---|
| **Estoque, compras, receitas, financeiro** | PostgreSQL (schema `dataload`) | Dados de domínio do app Frigus |
| **Histórico de conversa do assistente** | MongoDB (`agent_chats`) | Mensagens por sessão do chatbot (distinto do chat social do app, que já existe em `conversations`/`messages` no Postgres) |
| **Perfil comportamental** | MongoDB (`user_profiles`) | Resumo de hábitos gerado pela IA, chaveado por `users.id` |
| **Checkpointing do grafo** | LangGraph `MongoDBSaver` (`graph_checkpoints`/`graph_checkpoint_writes`) | Estado interno do grafo entre turnos, chaveado por `thread_id` (= `session_id`) — sobrevive a restart do processo |
| **Busca vetorial (RAG do FAQ)** | Qdrant | Índice do `Frigus-Documentacao.pdf` (`tools/qdrant/faq/`) |
| **Cache de perfil comportamental + rate limit de chat** | Redis | `tools/redis/perfil.py` (cache-aside sobre `user_profiles`) e `tools/redis/chat.py` (mensagens/minuto por usuário) |

Note que `users`, `groups`, `stocks` etc. no Postgres usam `INTEGER PRIMARY KEY` sem `SERIAL` (o DDL foi
desenhado para carga de dados) — os tools geram o próximo ID via `MAX(id)+1` (`tools/postgres/helpers.py::next_id`).

---

## API HTTP

`interfaces/api/` — FastAPI.

**Autenticação:** header `X-API-Key`, resolvido em `interfaces/api/auth.py`. O Redis guarda só
`sha256(key) -> user_id` (`tools/redis/api_key.py`) — a key em claro aparece uma única vez, na
resposta do `POST /keys`. Com `API_KEY_AUTH_ENABLED=false` (default) a dependência devolve
`DEMO_USER_ID`, para a TUI e a demo local rodarem sem key.

| Método | Rota | O que faz |
|---|---|---|
| `POST` | `/keys` | Emite API key para um usuário (cria usuário + grupo + estoque). Exige `X-Signup-Secret`; **409** se o usuário já tem key ativa |
| `POST` | `/chats` | Cria uma sessão de chat (`chat_id` + `stock_id` resolvido) |
| `POST` | `/chats/{chat_id}/messages` | Envia mensagem e roda o grafo. **429** + `Retry-After` se o rate limit do Redis estourar (10 msg/60s) |
| `POST` | `/chats/{chat_id}/messages/stream` | Mesma operação em **SSE**: um evento `no` por agente concluído, um evento `resposta` no fim |
| `GET` | `/chats/{chat_id}/messages` | Histórico da sessão (só do dono do `user_id` autenticado) |
| `DELETE` | `/chats/{chat_id}` | Encerra a sessão. **202** — o resumo da conversa e a atualização do perfil (duas chamadas de LLM) vão pra `BackgroundTasks`, fora do caminho da resposta |
| `GET` | `/health/live` | Liveness |
| `GET` | `/health/ready` | Readiness — checa Postgres/Mongo/Redis/Qdrant, **503** se algum estiver fora |
| `GET` | `/.well-known/agent-card.json` | Agent Card do A2A (discovery) |
| `POST` | `/a2a` | A2A `message/send` (JSON-RPC 2.0) — conversa com o grafo como agente externo |
| `POST` | `/mcp` | Servidor MCP (Streamable HTTP) com as tools de domínio |

Rate limit (**429** + `Retry-After`) e erro não previsto (**500** com mensagem genérica; traceback só
no log, nunca no corpo) são traduzidos por handlers registrados no app (`interfaces/api/main.py`) —
as rotas só escrevem o caminho feliz.

O streaming é **progresso por nó, não token a token**: quem escreve o texto final é o Guardrail de
Saída, que reescreve a resposta inteira depois que o LLM termina — não há token final para emitir
antes disso (`chat/runner.py::executar_stream`).

---

## MCP e A2A

**MCP** (`interfaces/mcp/server.py`) — as 18 tools de domínio (estoque, compras, receitas,
financeiro, FAQ) expostas como servidor MCP em `POST /mcp`, montado dentro da própria API para
reaproveitar o `X-API-Key`. As tools de Postgres leem `user_id`/`stock_id` de `contextvars` e nunca
dos argumentos, então um middleware ASGI resolve a identidade pelo header e abre o `session_context`
em volta da requisição — o equivalente ao que `chat/runner.py` faz por turno do grafo.

Detalhes que não são óbvios e estão comentados no código:

- O lifespan do app montado **não** é executado pelo FastAPI; sem encadeá-lo (`interfaces/api/main.py`)
  toda chamada morre em `Task group is not initialized`.
- `stateless_http=True` — sessão MCP de longa duração rodaria o handler em outra task, e o
  `session_context` do middleware não chegaria na tool.
- O SDK liga proteção contra DNS rebinding por padrão, com allowlist `localhost:*`. Em domínio real
  é preciso passar `host=` diferente de localhost, senão tudo responde **421**.

**A2A** (`interfaces/api/routes/a2a.py`) — Agent Card em `/.well-known/agent-card.json`, com uma
skill por domínio do grafo, e a operação `message/send` em `POST /a2a` (JSON-RPC 2.0). Escrito à mão,
sem o `a2a-sdk`: o card declara `streaming=false`/`pushNotifications=false`, então task store,
streaming e cancelamento — o que o SDK traz de fato — seriam código morto.

O `contextId` do A2A **é** o `session_id` do chat: é ele que faz duas chamadas caírem na mesma
conversa (mesmo `thread_id` no checkpointer). Sem `contextId`, a resposta devolve o id gerado para o
cliente reusar. O `user_id` não vem do protocolo — vem da mesma auth por `X-API-Key`.

Erro de protocolo (método desconhecido, params inválidos) volta como objeto `error` do JSON-RPC com
HTTP 200; auth e rate limit voltam como status HTTP (401/429), que é onde um cliente A2A espera
encontrá-los.

---

## Guardrails e Juiz

- **Guardrail de Entrada**: detecção determinística de prompt injection/acesso a dados internos →
  anonimização de PII → classificação por LLM (aprova, ou bloqueia por conteúdo ofensivo, perigoso,
  ilícito, político ou pedido de conselho médico).
- **Juiz**: audita grounding, relevância e completude da resposta antes dela sair; pode mandar o
  especialista tentar de novo (até 2 vezes).
- **Guardrail de Saída**: nunca bloqueia — redige PII remanescente e corrige afirmações de segurança
  alimentar/validade sem ressalva ou conselhos de saúde/nutrição clínica.

---

## Próximos passos (fora do escopo desta base)

- **A2A como cliente**: hoje o Frigus é servidor A2A (card + `message/send`). Consumir outro agente
  (ex. a agenda do assessor-ai) por A2A ainda está em discussão — ver TODO.md.
- **Redis — fila de tasks**: pendente, deliberadamente não implementado ainda (ver TODO.md). Os
  usos atuais (cache de perfil, rate limit, API keys) são leitura/escrita síncrona simples; uma fila
  de tasks é um uso diferente de Redis, ainda sem desenho definido.

---

## Configuração

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```env
GEMINI_API_KEY=...          # obrigatória
GROQ_API_KEY=...            # obrigatória
ANTHROPIC_API_KEY=...       # opcional
OPENROUTER_API_KEY=...      # opcional — 3º provider na cadeia de fallback
SPOONACULAR_API_KEY=...     # opcional — receitas externas
POSTGRES_URI=postgresql://frigus:frigus@localhost:5432/frigus
MONGODB_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333

API_KEY_AUTH_ENABLED=false  # true exige X-API-Key nas rotas de chat e no /mcp
SIGNUP_SECRET=...           # obrigatório para emitir key via POST /keys
A2A_BASE_URL=http://localhost:8000
```

### Instalação

```bash
uv venv
uv sync
```

### Subir a infraestrutura local

```bash
docker compose up -d
```

(O `main.py` também tenta subir os serviços sozinho via `config/docker.py`, assumindo Docker Desktop no Windows.)

### Execução

```bash
just run          # equivalente a `python main.py tui` (default)
just run api       # sobe a API (FastAPI/uvicorn) em localhost:8000 — sem auth ainda
```

### Desenvolvimento

```bash
just test         # pytest (não precisa de .env nem banco)
just check        # ruff check — mesmo lint que roda no CI
just fix          # ruff check --fix
```

Digite `/exit` para encerrar.

---

## Dependências principais

- [LangChain](https://github.com/langchain-ai/langchain) / [LangGraph](https://github.com/langchain-ai/langgraph)
- [qdrant-client](https://github.com/qdrant/qdrant-client) — busca vetorial para o RAG do FAQ
- [redis](https://github.com/redis/redis-py) — cache de perfil comportamental + rate limit de chat + API keys
- [psycopg2-binary](https://pypi.org/project/psycopg2-binary/) — Postgres
- [pymongo](https://pymongo.readthedocs.io/) — Mongo
- [Rich](https://github.com/Textualize/rich) + [pyfiglet](https://github.com/pwaller/pyfiglet) — banner/painéis da TUI
- [Textual](https://github.com/Textualize/textual) — interface TUI (`interfaces/tui/`), única interface interativa hoje
- [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) — API (`interfaces/api/`), com auth por `X-API-Key`
- [mcp](https://github.com/modelcontextprotocol/python-sdk) — SDK oficial do MCP (`MCPServer`), usado em `interfaces/mcp/`
- [httpx](https://www.python-httpx.org/) — client HTTP da Spoonacular Food API
- [Pydantic](https://docs.pydantic.dev/) — validação de schemas das tools
- `langchain-anthropic`, `langchain-google-genai`, `langchain-groq`, `langchain-openai` (OpenRouter, via base URL compatível) — integrações com providers
