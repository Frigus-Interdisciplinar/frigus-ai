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

Para tudo fora desses domínios (small talk, perguntas fora de escopo), o roteador (LLM) responde
diretamente ao usuário.

---

=======
## Arquitetura

Visão de alto nível: quem chama, o que a API expõe, o grafo de agentes e onde cada dado mora.

```mermaid
flowchart TB
    subgraph CLI["Clientes"]
        WEB["Web (React)"]
        TUI["TUI (Textual)"]
        EXT["Clientes MCP / A2A"]
    end

    subgraph API["API FastAPI"]
        AUTH["Auth: Firebase (Bearer) ou X-API-Key<br/>rate limit (fastapi-guard)"]
        V1["/v1: chats, stock, shopping,<br/>recipes, profile"]
        PROT["/a2a e /mcp (20 tools)"]
        OPS["/health e /metrics"]
    end

    SVC["services: chat_service, runner<br/>(ponto único de todas as interfaces)"]

    subgraph GRAFO["Grafo LangGraph"]
        GE["Guardrail de entrada"] --> RT["Roteador"]
        RT --> ESP["Especialistas: estoque, compras,<br/>receitas, faq, financeiro"]
        RT --> ASS["Assessor (agente remoto)"]
        GE -. "foto" .-> VIS["Visão"]
        ESP --> ORQ["Orquestrador"]
        ORQ --> JZ["Juiz (até 2 retentativas)"]
        ESP --> JZ
        VIS --> ORQ
        ASS --> JZ
        JZ --> GS["Guardrail de saída"]
    end

    subgraph DADOS["Persistência"]
        PG[("Postgres / Supabase<br/>estoque, compras, finanças, identidade")]
        MG[("MongoDB<br/>histórico, fatos, checkpoints")]
        RD[("Redis<br/>rate limit, cache do guardrail,<br/>ranking de desperdício, API keys")]
        QD[("Qdrant<br/>RAG do FAQ, resumos de chats")]
        N4[("Neo4j<br/>grafo de receitas")]
    end

    subgraph EXTERNO["Serviços externos"]
        LLM["LLMs: Gemini, Groq,<br/>Vercel AI Gateway (GPT-6 Luna, JeV)"]
        SPOON["Spoonacular"]
        ASSR["Assessor financeiro (A2A)"]
        FB["Firebase Auth"]
    end

    subgraph OBS["Observabilidade"]
        PROM["Prometheus (SLO e alertas)"] --> GRAF["Grafana"]
        LS["LangSmith (traces)"]
    end

    CLI --> AUTH --> V1 & PROT
    V1 & PROT --> SVC --> GRAFO
    AUTH -.-> FB
    AUTH -.-> RD
    GRAFO --> LLM
    ESP --> PG & RD & QD & N4 & SPOON
    ASS --> ASSR
    SVC --> MG
    GRAFO -. "checkpoints" .-> MG
    OPS -. "scrape" .-> PROM
    GRAFO -. "traces" .-> LS
```


## Grafo de agentes

<div align="center">
  <img src="assets/diagrama-agentes.png" alt="Diagrama do fluxo de agentes do Frigus.AI" width="720" />
</div>

O **Roteador** pode escolher mais de um especialista para o mesmo pedido (só quando as consultas são
independentes); eles rodam em paralelo e o **Orquestrador** espera todos para montar uma única resposta.
Com o JeV (`LLM__GATEWAY__API_KEY`), a escolha é uma pergunta sim/não por especialista, todas numa
requisição só; o LLM entra quando nenhum passa (saudação, fora de escopo, clarificação) ou quando o
pedido depende de etapas, porque aí é preciso escrever a resposta.
Um especialista de texto (receitas, faq, assessor) que responde sozinho passa direto, sem chamada extra de LLM.

O **Juiz** audita a resposta quanto a grounding (só usa dados que vieram das
tools), relevância e completude, ANTES do guardrail de saída. Se reprovar, a resposta volta para o
**orquestrador** (com o motivo da reprovação), até 2 tentativas — os especialistas não rodam de novo, para
não regravar estoque nem lista de compras. Depois disso, segue mesmo reprovado (loga um aviso), para nunca
travar o usuário. O que ele confere é o retorno das tools (não o texto do especialista), e falha na
avaliação vira `INDISPONIVEL`, não aprovação. O avaliador é o JeV (grounding como escolha entre
sustentada/contradiz/sem evidência, relevância e completude como sim/não, veredito calculado em
Python e feedback de uma frase fixa por critério) ou, sem gateway ou se ele falhar, um LLM com
justificativa livre.

---

## Estrutura do projeto

```
frigus-ai/
├── pyproject.toml / uv.lock
├── docker-compose.yml               # Postgres, Mongo, Redis, Neo4j e Qdrant; profile `observability`: Prometheus + Grafana
├── justfile                         # run, web, obs, test, check, fix, deploy
├── scripts/                         # run.sh (sobe o Docker e a app) e prometheus_token.py (token do /metrics)
├── data/
│   ├── pdf/Frigus-Documentacao.pdf  # fonte do RAG
│   └── sql/schema.sql               # Espelho do schema public do Supabase (DDL)
├── observability/
│   ├── prometheus/                  # scrape, regras de SLO e alertas
│   ├── grafana/                     # datasource e dashboard (inclui os painéis do JeV)
│   └── RELATORIO.md                 # cenários, SRE e sessões contra a infra real
├── web/                             # Painel React (Vite): chat com a timeline de execução, perfil e /metrics
├── tests/                           # Espelha a estrutura do pacote
│
└── src/frigus_ai/                   # Pacote instalável com o "cérebro" do assistente
    │
    ├── main.py                      # Dispatcher — `python -m frigus_ai.main <tui|api>`
    ├── tui/                         # app.py (Textual) + display.py + app.tcss
    ├── api/                         # FastAPI: app.py, deps.py, lifespan.py, mcp.py, auth/ (Firebase + X-API-Key),
    │                                # routes/{v1,auth,health,metrics,a2a}, middleware/, errors/
    ├── services/                    # Casos de uso, usados por toda interface: chat_service, runner, user_service,
    │                                # auth_service e stock/shopping/recipe_service (atrás das rotas v1)
    ├── repositories/                # Persistência: Postgres via SQLAlchemy (@transacional) e Mongo
    ├── schemas/                     # Contratos HTTP (chat, stock, shopping, recipes, a2a, eventos de execução)
    ├── domain/                      # Modelos, tipos de ID, erros e privacy.py (PII: anonimizar/desanonimizar/redigir)
    ├── settings/                    # Config única (pydantic-settings): api, api_keys, database, llm, observability
    ├── telemetry/                   # Métricas Prometheus de runtime e evals/ (sre_report.py, harness de cenários)
    │
    ├── graph/
    │   ├── state.py                 # Estado + EntradaGrafo/SaidaGrafo, os *Update de cada node
    │   │                            # e o contrato AsyncNode[R]; Route (Literal + constantes)
    │   ├── names.py                 # Nomes dos nodes. Fora de nodes/ de propósito: state.py importa
    │   │                            # daqui, e de dentro do pacote daria ciclo de import
    │   ├── llm.py                   # Instâncias de LLM e cadeias de fallback
    │   ├── agents.py                # Agentes compilados (create_agent por especialista)
    │   ├── builder.py               # Grafo (ciclo de reescrita do Juiz) + checkpointer Mongo
    │   ├── prompts/                 # Só .md + __init__.py — nenhum outro .py na pasta
    │   │   ├── __init__.py          # load_prompt()/load_sections(): seções `## NOME` do .md
    │   │   ├── sistema.md           # persona, data, tools obrigatórias, fatos e conversas
    │   │   ├── router.md / estoque.md / compras.md / receitas.md / faq.md / financeiro.md
    │   │   │                        # router.md tem também as perguntas do JeV (*_JEV)
    │   │   ├── orquestrador.md
    │   │   ├── juiz.md              # PAPEL + SHOTS + TEMPLATE (à parte) + perguntas do JeV (*_JEV)
    │   │   ├── guardrail.md         # CLASSIFICADOR + INSTRUCAO_JEV + COMPLIANCE (load_sections cru)
    │   │   └── fatos.md / resumidor.md / visao.md
    │   ├── nodes/                   # Funções de nó do grafo LangGraph
    │   │   ├── contexto.py          # responder()/responder_com_evidencias() p/ agente, perguntar() p/ LLM cru,
    │   │   │                        # mensagens_do_turno() e podar_historico() (teto do checkpoint)
    │   │   ├── especialista.py      # @especialista e especialista_com_agente (monta o update dos especialistas)
    │   │   ├── router.py / estoque.py / compras.py / receitas.py / faq.py / financeiro.py / assessor.py
    │   │   └── orquestrador.py / juiz.py / visao.py
    │   ├── guardrail/               # Subsistema próprio, fora de nodes/: os nós são só a porta
    │   │   ├── entrada.py           # nó: anonimiza, detecta ataque, classifica (com cache)
    │   │   ├── saida.py             # nó: redige PII e revisa a resposta
    │   │   ├── padroes.py           # regex de jailbreak + keywords de dado interno
    │   │   ├── schemas.py           # Categoria, DESCRICAO_CATEGORIA, Motivo, RESPOSTAS_BLOQUEIO
    │   │   └── cache.py             # veredito do classificador no Redis (evita chamada repetida)
    │   └── tools/                   # Tools do LLM por domínio (schemas.py + repo.py): estoque, compras,
    │                                # receitas, financeiro, faq (RAG), preferencias (Neo4j), spoonacular
    │
    └── infra/                       # Conexões lazy e clientes externos
        ├── postgres/                # Engine SQLAlchemy, contextvars de usuário/estoque e models (Supabase, schema public)
        ├── mongo/ / redis/ / qdrant/ / neo4j/ / firebase/ / spoonacular/
        ├── assessor/                # Cliente A2A do Assessor financeiro
        ├── llm/                     # build_llm + registry de providers; jev/ = JeV pela Decisions API do gateway
        └── logging/
```

## Persistência

| Camada | Tecnologia | Responsabilidade |
|---|---|---|
| **Estoque, compras, receitas, financeiro** | PostgreSQL no Supabase (schema `public`) | Dados de domínio do app Frigus |
| **Histórico de conversa do assistente** | MongoDB (`agent_chats`) | Mensagens por sessão do chatbot (distinto do chat social do app, que já existe em `conversations`/`messages` no Postgres) |
| **Fatos estruturados do usuário** | MongoDB (`user_fatos`) | Alergias/preferências/restrições/hábitos extraídos do chat, chaveado por `users.id` |
| **Checkpointing do grafo** | LangGraph `MongoDBSaver` (`graph_checkpoints`/`graph_checkpoint_writes`) | Estado interno do grafo entre turnos, chaveado por `thread_id` (= `session_id`) — sobrevive a restart do processo |
| **Busca vetorial (RAG do FAQ)** | Qdrant | Índice do `Frigus-Documentacao.pdf` (`graph/tools/faq/`) |
| **Rate limit, cache e ranking** | Redis | Mensagens/minuto por usuário, cache do guardrail, ranking de desperdício e API keys (`infra/redis/`) |

Note que `users`, `groups` e `shopping_lists` usam `UUID` (`gen_random_uuid()`) e as demais tabelas
usam sequence — os IDs vêm do banco.

---

## API HTTP

`src/frigus_ai/api/` — FastAPI. Autenticação condicional (`API__KEY_AUTH_ENABLED`): ligada, o
usuário vem do login do app Frigus (`Authorization: Bearer`, token do Firebase, casado por email) ou
da `X-API-Key` (MCP, A2A e integrações); desligada (modo local/demo), reaproveita ou cria um usuário
local único.

Rotas de domínio (`chats`, `keys`, `stock`, `shopping-list`, `recipes`, `profile`) ficam sob
`/v1`; `/health`, `/metrics`, A2A (`/a2a`, `/.well-known/agent-card.json`) e MCP (`/mcp`) ficam na raiz.

| Método | Rota | O que faz |
|---|---|---|
| `POST` | `/v1/chats` | Cria uma sessão de chat (`chat_id` + `stock_id` resolvido) |
| `GET` | `/v1/chats` | Lista os chats do usuário |
| `POST` | `/v1/chats/{chat_id}/messages` | Envia mensagem e roda o grafo. **429** + `Retry-After` se o rate limit do Redis estourar (10 msg/60s) |
| `POST` | `/v1/chats/{chat_id}/messages/stream` | Mesmo turno em SSE, com a timeline de execução do grafo |
| `GET` | `/v1/chats/{chat_id}/messages` | Histórico da sessão |
| `DELETE` | `/v1/chats/{chat_id}` | Encerra a sessão. **202** — o resumo da conversa (chamada de LLM) vai pra `BackgroundTasks`, fora do caminho da resposta |
| `GET` / `POST` / `PUT` / `DELETE` | `/v1/stock/items`, `/v1/stock/items/{item_id}` | Lista, adiciona, atualiza a quantidade e descarta itens do estoque |
| `POST` | `/v1/stock/foto` | Analisa a foto da geladeira (nó de visão) |
| `GET` / `POST` / `PUT` | `/v1/shopping-list/items`, `/v1/shopping-list/items/{item_id}/bought` | Lista de compras |
| `GET` | `/v1/recipes`, `/v1/recipes/suggestions` | Receitas e sugestões com o que há no estoque |
| `GET` / `PUT` | `/v1/profile` | Perfil alimentar (alergias, preferências, restrições, hábitos) |
| `POST` / `DELETE` | `/keys`, `/keys/rotate` | Emite, rotaciona e revoga a API key (exige `SIGNUP_SECRET` na emissão) |
| `POST` / `GET` | `/a2a`, `/.well-known/agent-card.json` | Agente A2A e seu card |
| `GET` | `/health/live`, `/health/ready` | Liveness e readiness — checa Postgres/Mongo/Redis/Qdrant, **503** se algum estiver fora |
| `GET` | `/metrics` | Métricas Prometheus (Bearer com `API_KEYS__METRICS_TOKEN`, se configurado) |
| — | `/mcp` | Servidor MCP com as tools de domínio (identidade por `X-API-Key`) |

Erro não previsto devolve **500** com mensagem genérica; o traceback vai pro log, nunca pro corpo da
resposta (evita vazar mensagem crua de psycopg2/pymongo pro cliente).

---

## Guardrails e Juiz

- **Guardrail de Entrada**: detecção determinística de prompt injection/acesso a dados internos →
  anonimização de PII → classificação (aprova, ou bloqueia por conteúdo ofensivo, perigoso, ilícito,
  político ou pedido de conselho médico). Com `LLM__GATEWAY__API_KEY`, quem classifica é o JeV
  (decisão tipada, sem gerar texto, `infra/llm/jev/`); sem ela, a cadeia de LLMs. O JeV também
  escolhe os especialistas no roteador e avalia a resposta no juiz, sempre com o LLM de reserva.
- **Juiz**: audita grounding (contra o retorno das tools), relevância e completude da resposta antes
  dela sair; pode mandar o orquestrador reescrever (até 2 vezes).
- **Guardrail de Saída**: nunca bloqueia — redige PII remanescente e corrige afirmações de segurança
  alimentar/validade sem ressalva ou conselhos de saúde/nutrição clínica.

---

## Próximos passos

O que ainda falta, e por quê, está em `.agents/notes/pending/` (comece por `requisitos-disciplina/`).
Em resumo:

- **Configuração externa:** credencial do Firebase, cartão na conta Vercel (para o Luna e o JeV
  responderem) e uma instância de Neo4j.
- **JeV:** triagem do guardrail de saída, categoria e resolução de nome de produto
  (`.agents/notes/pending/jev/`).
- **Neo4j:** sincronização automática Postgres → grafo de receitas.
- **SLOs:** latência e erro só passam fora do plano gratuito dos LLMs (`observability/RELATORIO.md`).

---

## Configuração

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha (o prefixo antes de `__` é o grupo de `settings/`):

```env
LLM__GEMINI__API_KEY=...          # obrigatória
LLM__GROQ__API_KEY=...            # obrigatória
LLM__CLAUDE__API_KEY=...       # opcional
LLM__OPENROUTER__API_KEY=...      # opcional — último provider na cadeia de fallback
LLM__GATEWAY__API_KEY=...      # opcional — Vercel AI Gateway: GPT-6 Luna na cadeia; JeV no guardrail, roteador e juiz
API_KEYS__FIREBASE_PROJECT_ID=...   # login do app Frigus (Bearer): project_info.project_id do google-services.json
API_KEYS__METRICS_TOKEN=...      # opcional — exige Bearer no /metrics; o `just obs` repassa ao Prometheus
API_KEYS__SPOONACULAR_API_KEY=...     # opcional — receitas externas
DATABASE__POSTGRES_URI=postgresql://frigus:frigus@localhost:5432/frigus
DATABASE__MONGODB_URI=mongodb://localhost:27017
DATABASE__REDIS_URL=redis://localhost:6379/0
DATABASE__QDRANT_URL=http://localhost:6333
```

### Instalação

```bash
uv venv
uv sync
```

### Subir a infraestrutura local

```bash
docker compose up -d
just obs   # opcional: Prometheus (9090) + Grafana (3000), já com o token do /metrics
```

(O `just run` também sobe os serviços sozinho via `scripts/run.sh`, assumindo Docker Desktop.)

### Execução

```bash
just run          # equivalente a `python -m frigus_ai.main tui` (default)
just run api       # sobe a API (FastAPI/uvicorn) em localhost:8000; auth só com API__KEY_AUTH_ENABLED=true
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
- [redis](https://github.com/redis/redis-py) — rate limit, cache do guardrail, ranking de desperdício e API keys
- [SQLAlchemy](https://www.sqlalchemy.org/) + [psycopg2-binary](https://pypi.org/project/psycopg2-binary/) + [Alembic](https://alembic.sqlalchemy.org/) — Postgres
- [pymongo](https://pymongo.readthedocs.io/) — Mongo (histórico, fatos e checkpoints)
- [neomodel](https://neomodel.readthedocs.io/) — grafo de receitas no Neo4j
- [firebase-admin](https://firebase.google.com/docs/admin/setup) — valida o login do app Frigus
- [fastapi-guard](https://github.com/rennf93/fastapi-guard) — rate limit por rota e proteção da API
- [mcp](https://github.com/modelcontextprotocol/python-sdk) — servidor MCP
- [prometheus-client](https://github.com/prometheus/client_python) — métricas de runtime
- [Rich](https://github.com/Textualize/rich) + [pyfiglet](https://github.com/pwaller/pyfiglet) — banner/painéis da TUI
- [Textual](https://github.com/Textualize/textual) — interface TUI (`tui/`), única interface interativa hoje
- [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) — API (`api/`)
- [httpx](https://www.python-httpx.org/) — client HTTP da Spoonacular Food API
- [Pydantic](https://docs.pydantic.dev/) — validação de schemas das tools
- `langchain-anthropic`, `langchain-google-genai`, `langchain-groq`, `langchain-openai` (OpenRouter e Vercel AI Gateway, via base URL compatível) — integrações com providers
