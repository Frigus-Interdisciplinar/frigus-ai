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
├── interfaces/api/                  # main.py (FastAPI) + routes/{chats,health}.py + schemas/ — esqueleto, sem auth
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
    │   ├── runner.py                # Invoca o grafo e extrai a resposta
    │   └── service.py               # send_message, get_history, iniciar/encerrar_sessao
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
        ├── redis/                   # cache de perfil (perfil.py) + rate limit de chat (chat.py)
        └── qdrant/faq/              # RAG (Qdrant) sobre Frigus-Documentacao.pdf — connection/core/ingest
```

`api/`, `mcp_server/` e `a2a_server/` foram removidos — eram placeholders vazios. Serão recriados
quando cada trabalho começar (ver "Próximos passos").

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

As pastas `mcp_server/` e `a2a_server/` existem só com um `__init__.py` — são os pontos de extensão
reservados para quando fizer sentido:

- **MCP**: expor as tools do Frigus.AI para hosts MCP (Claude Desktop etc.).
- **A2A**: expor o grafo como um agente Agent-to-Agent para outros sistemas multi-agente.
- **Redis — fila de tasks**: pendente, deliberadamente não implementado ainda (ver TODO.md). Os dois
  usos atuais (cache de perfil, rate limit) são leitura/escrita síncrona simples; uma fila de tasks
  (ex. processar ingestão do Qdrant ou chamadas de MCP fora do caminho da requisição) é um uso
  diferente de Redis, ainda sem desenho definido.

---

## Configuração

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...
ANTHROPIC_API_KEY=...
POSTGRES_URI=postgresql://frigus:frigus@localhost:5432/frigus
MONGODB_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
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
just run api       # sobe a API (FastAPI/uvicorn) em localhost:8000 — esqueleto, sem auth ainda
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
- [redis](https://github.com/redis/redis-py) — cache de perfil comportamental + rate limit de chat
- [psycopg2-binary](https://pypi.org/project/psycopg2-binary/) — Postgres
- [pymongo](https://pymongo.readthedocs.io/) — Mongo
- [Rich](https://github.com/Textualize/rich) + [pyfiglet](https://github.com/pwaller/pyfiglet) — banner/painéis da TUI
- [Textual](https://github.com/Textualize/textual) — interface TUI (`interfaces/tui/`), única interface interativa hoje
- [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) — API (`interfaces/api/`), esqueleto sem auth
- [Pydantic](https://docs.pydantic.dev/) — validação de schemas das tools
- `langchain-anthropic`, `langchain-google-genai`, `langchain-groq` — integrações com providers
