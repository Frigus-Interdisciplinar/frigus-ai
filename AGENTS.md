# AGENTS.md

Contexto do projeto **Frigus.AI** para agentes de IA (Claude Code, Copilot, etc.) trabalhando neste
repositório.

## O que é

Assistente conversacional multi-agente do app **Frigus** (gestão de alimentos em geladeira/freezer/
despensa, compras, receitas e finanças domésticas). Construído com LangChain + LangGraph, RAG
(Qdrant) e um agente juiz (LLM-as-judge) para mitigar alucinação. Também é o **projeto da disciplina
de Sistemas Multiagentes** — ver seção "Requisitos da disciplina" abaixo para o que precisa ser
entregue e o que já está feito.

`main.py` é um dispatcher fino (`python main.py <interface>`) — a lógica de montar estado, invocar o
grafo e persistir histórico vive em `frigus_ai.chat.service`, compartilhada por todas as interfaces
(`tui`, `api`). Detalhes de arquitetura, fluxo de agentes e tools estão no [README.md](README.md) —
leia-o antes de mexer em `agents/` ou `graph/`.

## Requisitos da disciplina

Baseado no enunciado do trabalho ("mínimo para 7,0" + extra). Cada item marca o que já está feito
neste repo e onde. Antes de reportar algo como pendente, confira o código — este checklist pode
ficar desatualizado.

| Requisito | Status | Onde |
|---|---|---|
| API FastAPI/Flask | ⚠️ Parcial | `interfaces/api/` — esqueleto de rotas (`/health`, `/chats`) rodando, sem autenticação/rate limiting ainda (ver TODO.md) |
| Multiagente, mínimo 5 agentes | ✅ Feito | 10 nós no grafo: guardrail entrada/saída, router, estoque, compras, receitas, faq, financeiro, orquestrador, juiz (`agents/nodes/names.py`) |
| LangChain para criação dos agentes | ✅ Feito | `graph/agents.py` |
| LangGraph para orquestração | ✅ Feito | `graph/builder.py` |
| Controle de sessões por usuário | ⚠️ Parcial | `thread_id=session_id` no checkpointer LangGraph + histórico em Mongo (`tools/mongo/chats`). Checkpointer agora é `MongoDBSaver` (`graph/builder.py`) — estado sobrevive a restart. Falta só sessão HTTP de verdade, que depende da API |
| Memória de longo prazo | ⚠️ Parcial | `tools/mongo/users` — perfil comportamental (resumo de hábitos) por `user_id`, persistente no Mongo. Avaliar se cobre o requisito ou se precisa de algo além do resumo (ex. memória vetorial) |
| MCP, A2A (integrações com sistemas/agentes externos) | ❌ Pendente | Nada implementado — as pastas placeholder foram removidas do repo, serão recriadas quando o trabalho começar. Ver TODO.md |
| RAG com fonte externa indicada | ✅ Feito | `tools/qdrant/faq/` — Qdrant sobre `data/pdf/Frigus-Documentacao.pdf` (fonte local, categoria explicitamente aceita pelo enunciado) |
| Agente juiz (mitigação de alucinação) | ✅ Feito | `agents/nodes/juiz.py` — audita grounding/relevância/completude, até 2 retentativas |
| Guardrail | ✅ Feito | `agents/nodes/guardrail/{entrada,saida}.py` |
| Observabilidade/SRE — custo estimado (100 e 1000 usuários/semana) | ❌ Pendente | ver TODO.md |
| Observabilidade/SRE — latência interagentes e tempo total de resposta | ⚠️ Parcial | Tracing via LangSmith ligado (`config/settings.py`, `chat/runner.py`, `chat/repositories.py`) — dado já disponível no dashboard, falta só consultar/reportar |
| Observabilidade/SRE — índice de erros | ❌ Pendente | |
| Observabilidade/SRE — custo/ROI | ❌ Pendente | |
| Observabilidade/SRE — custo por resolução | ❌ Pendente | |
| Desenho de arquitetura de alto nível | ✅ Feito | README.md — diagrama Mermaid + `assets/diagrama-agentes.png` |
| Extra: complexidade do projeto | Em andamento | 5 domínios de negócio + guardrail duplo + juiz já é acima da média; MCP/A2A/observabilidade (pendentes acima) são o que mais soma aqui |

**Importante:** a escola não paga API de IA generativa — por isso o projeto já usa só providers com
tier gratuito viável (Gemini, Groq) e Claude/Anthropic como opcional (`ANTHROPIC_API_KEY` tem
default vazio em `config/settings.py`, então o projeto roda sem ela).

## Stack

- Python 3.13+, gerenciado com `uv` (`uv venv`, `uv sync`, `uv add <pkg>`)
- LangChain 1.2 / LangGraph 1.1 para orquestração de agentes
- LLMs: Gemini (`gemini-2.5-flash`), Groq (`llama-3.3-70b-versatile`, `qwen-2.5-pro`), Claude
  (`claude-haiku-4-5`, `claude-sonnet-4-6`) e OpenRouter (`z-ai/glm-5.2:free`) mapeados em
  `config/models.py`. Provider sem API key configurada faz `build_llm` devolver `None` e fica fora
  da cadeia de fallback — só Gemini e Groq são obrigatórios
- PostgreSQL (via Docker, auto start/stop em `config/docker.py`) para estoque/compras/receitas/
  financeiro, acessado via `psycopg2` cru (schema `dataload`, DDL fornecido em `data/sql/schema.sql`)
- MongoDB para histórico de conversa (`tools/mongo/chats`), perfil comportamental
  (`tools/mongo/users`) e checkpoint do LangGraph (`MongoDBSaver`, coleções `graph_checkpoints`/
  `graph_checkpoint_writes`)
- Qdrant para RAG do FAQ sobre `data/pdf/Frigus-Documentacao.pdf` (`tools/qdrant/faq/`)
- Redis para cache do perfil comportamental e rate limit de chat (`tools/redis/`) — fila de tasks
  ainda não implementada, ver TODO.md
- `pytest` (`tests/`, espelhando a estrutura do pacote) + `ruff` (lint) + CI no GitHub Actions
  (`.github/workflows/ci.yml`)

## Estrutura

```text
src/frigus_ai/          o "cérebro" do assistente, pacote instalável (hatchling, layout src/)
├── agents/
│   ├── prompts/         só .md + loader.py — load_prompt()/load_sections() montam o system_prompt
│   │                     a partir de frontmatter (metadados) + seções `## NOME` do corpo
│   └── nodes/           nós de grafo — um arquivo por agente/domínio
├── graph/               state.py (estado + Route), llm.py (builders), agents.py (agentes compilados), builder.py (grafo)
├── tools/                integrações externas: tools/postgres/{estoque,compras,receitas,financeiro},
│                         tools/mongo/{chats,users}, tools/qdrant/faq/, tools/redis/
└── chat/                models.py (contrato de mensagem), repositories.py (Mongo), runner.py (invoca o grafo), service.py (casos de uso)

interfaces/tui/         app.py (Textual) + display.py (Bubble/MessageRow) + app.tcss — única interface interativa
interfaces/api/         main.py (FastAPI) + routes/{chats,health}.py + schemas/ — esqueleto, sem auth ainda
config/                 settings.py (env vars via pydantic-settings), models.py (Model enum + providers), docker.py, logging.py
data/                   pdf/Frigus-Documentacao.pdf (RAG) + sql/schema.sql (DDL fornecido)
main.py                 dispatcher fino — `python main.py <interface>` (`tui` [default] ou `api`)
```

Padrão de cada domínio de tool: `schemas.py` (Pydantic) + `core.py` (as tools em si), com
`connection.py`/`context.py`/`helpers.py` compartilhados em `tools/postgres/`. Siga esse padrão para
qualquer tool nova (redis, qdrant, etc).

Nenhuma interface (`interfaces/*`) deve chamar `frigus_ai.graph.builder`, `frigus_ai.tools.mongo.*`
ou `frigus_ai.tools.postgres.*` diretamente — sempre via `frigus_ai.chat.service`. É esse limite que
permite API/TUI existirem sem duplicar a lógica de montar estado, invocar o grafo e persistir
histórico. `interfaces/api/routes/chats.py` segue essa regra hoje, mas ainda não tem autenticação —
`user_id` é sempre `DEMO_USER_ID` (ver TODO.md).

`interfaces/terminal/` foi removido — a TUI (Textual) é a única interface interativa agora.
`mcp_server/` e `a2a_server/` continuam só placeholders vazios removidos do repo — recriar quando o
trabalho de cada um começar (ver TODO.md).

## Convenções

- **Leia o código antes de escrever código.** Antes de mudar qualquer arquivo, leia-o inteiro e leia
  quem o chama. O padrão do repo está no código, não na sua cabeça: se um módulo já resolve o
  problema de um jeito, o jeito certo é o dele. Faça a mudança caber no arquivo — não o contrário.
  Se a sua mudança precisa de uma forma diferente da que já está ali, isso é sinal de que você
  entendeu errado o problema, não de que o arquivo está errado. Confirme antes de divergir.

  **Exemplo real (não repetir):** ao adicionar OpenRouter, `graph/llm.py` era uma coluna alinhada de
  one-liners (`llm_x = build_llm(...)`) e `build_llm` já era orientado a tabela (`PROVIDER_MAP`,
  `API_KEYS`, `BUILDERS`) com o tratamento por provider dentro da função. A primeira versão
  adicionou no nível do módulo um ternário multi-linha, uma variável `_fallbacks` e um bloco de
  comentário — quebrou o alinhamento e espalhou por fora o que a função já sabia fazer. O certo era
  duas linhas dentro de `build_llm` (`if not api_key: return None`) e uma linha na coluna, como
  todas as outras. **A regra que falhou foi de leitura, não de digitação.**

- **Entenda o que o código faz de verdade, não o que o nome sugere.** Rode, grepe os callers, leia o
  arquivo de teste. Achados que só apareceram por leitura real: a API não subia (`Role` do domínio
  shadowando o `Role` do schema em `interfaces/api/schemas/chat.py`); o rate limit funcionava mas a
  rota devolvia 500 em vez de 429; `.agents/skills/fastapi.md` documentava como decisão deliberada
  um padrão (`rotas são def`) que a Fase 2 do async já tinha invertido. Nenhum apareceria lendo só
  o nome das funções.

- **Não construa infra para dado que o sistema não coleta.** Antes de propor integração nova, grepe
  o schema e as tools atrás da entrada dela. Casos já barrados por essa regra: resolução de produto
  por código de barras (não existe coluna de código de barras em `data/sql/schema.sql`, e a leitura
  de NF-e é stub) e o grafo de preferências no Neo4j (`DISLIKES`/`ALLERGIC_TO` não são campo em
  lugar nenhum — o perfil no Mongo é texto livre). Ver TODO.md.

- Código de domínio (nomes de função, variáveis, docstrings de tool, mensagens ao usuário) é em
  **português**; nomes de classes/tipos de infraestrutura (`Settings`, `Model`, `Route`) em inglês.
  Siga o idioma já usado no arquivo que você está editando.
- Enums de domínio usam `StrEnum` (ver `agents/nodes/guardrail/schemas.py:Categoria`,
  `chat/models.py:Role`). **Exceção:** `graph/state.py:Route` e `agents/nodes/names.py:Node` são
  `Literal` + classe de constantes (não `StrEnum`) — valores guardados em `Estado` (checkpointado
  pelo `MongoDBSaver`) precisam ser `str` puro pro msgpack, sem allowlist extra
  (`LANGGRAPH_ALLOWED_MSGPACK_MODULES` foi removido de `graph/builder.py` por causa disso).
- Conexões com banco (Postgres, Mongo) são **lazy** — inicializadas só na primeira operação, nunca
  no import do módulo. Mantenha esse padrão para novas integrações (Redis, Qdrant, MCP, A2A).
- Tools retornam a classe `Response` (`tools/response.py`) para padronizar sucesso/erro.
- **Tools do LLM nunca recebem `user_id`/`stock_id` como argumento.** Args de tool são escolhidos
  pelo LLM via tool-calling — qualquer dado de escopo/permissão não pode vir por ali. O padrão é um
  `contextvars.ContextVar` setado uma vez por request (`tools/postgres/context.py:session_context`,
  chamado em `chat/runner.py:executar`) e lido dentro da tool. Ver uso em
  `tools/postgres/{estoque,compras,receitas,financeiro}/core.py`.
- Não commitar `.env`; usar `.env.example` como referência de variáveis novas.
- **Simplicidade acima de tudo.** Projeto de disciplina em estágio inicial — prefira a solução direta
  à abstração "flexível para o futuro". Sem camada genérica, sem config plugável, sem interface para
  uma única implementação. Isso vale tanto para código de domínio quanto para infra.

## Fluxo de trabalho (Git)

- Mudança de qualquer tamanho (feature, fix, refactor) vai em **branch própria**, nunca commit
  direto em `main` — exceção só pra coisas triviais tipo ajuste de README/badge.
- Nome de branch segue `tipo/slug-curto`, mesmo padrão já usado no repo (`feat/big-bang`,
  `feat/chatbot-multiagentes`, `docs/melhorias-readme`). Tipos comuns: `feat`, `fix`, `refactor`,
  `docs`, `chore`.
- Commits seguem o padrão `tipo: descrição curta` (`feat:`, `fix:`, `docs:`, `chore:`) — ver
  `git log` para exemplos reais.
- Mudança termina em **Pull Request** para `main` — mantém o histórico navegável e dá um ponto de
  review antes do merge.
- **Toda feature nova vem com pelo menos um teste.** Não é gate automático de CI (ainda) — é norma
  de review: se o PR adiciona comportamento e não tem teste nenhum, o teste vem junto ou o PR
  explica por que não dá. Alvo é a lógica de decisão (branch, parser, cálculo, regra de negócio),
  não getter/wrapper trivial. Se a coisa só é testável com banco/LLM real, mocke a fronteira (ver
  `tests/agents/nodes/guardrail/test_entrada.py`, que cobre só os caminhos determinísticos).
- Pegadinha nova de lib vira entrada em `.agents/skills/<lib>.md`.

## Padrões de organização e clean code

- **Single responsibility por nó de agente.** `agents/nodes/` (execução) fica separado de
  `agents/prompts/` (conteúdo/persona) — mudar o texto de um prompt nunca deveria exigir tocar na
  lógica de roteamento do grafo, e vice-versa.
- **Contrato de retorno único.** Tools não retornam dict cru nem deixam exception vazar para o
  agente — usam `Response` (`tools/response.py`). Ao criar tool nova, reusar essa classe.
- **Config centralizada.** Uma única fonte de env vars (`config/settings.py`, `pydantic-settings`) e
  um único enum fechado de modelos/providers (`config/models.py:Model`/`PROVIDER_MAP`). Não ler
  `os.environ` direto em outros módulos.
- **Ciclo de retentativa do Juiz é explícito no grafo**, não escondido em loop Python — ver
  `decidir_apos_juiz` em `graph/builder.py`. Qualquer novo especialista que produza resposta ao
  usuário deve passar pelo Juiz antes do Guardrail de Saída, seguindo esse mesmo padrão de edge
  condicional.

## Comandos

```bash
uv venv && uv sync   # instalar dependências
just run             # sobe a TUI (sobe Postgres/Mongo/Redis/Qdrant via Docker automaticamente)
just run api          # sobe a API (FastAPI/uvicorn, localhost:8000)
just test            # suíte de testes (não precisa de .env nem banco)
just check           # lint (roda no CI em push/PR pra main); `just fix` aplica o que dá
```

`just run` chama o console script `frigus-ai` (`[project.scripts]`), que é o mesmo
`python main.py tui`. Ver `justfile` para as demais receitas.

## Ao adicionar uma tool nova

1. Criar `tools/<sistema>/<domínio>/schemas.py` com os modelos Pydantic de entrada/saída.
2. Criar `tools/<sistema>/<domínio>/core.py` com as funções decoradas como tool (ver
   `config/decorators.py:log_tool`).
3. Se for um serviço externo com estado de conexão, criar `connection.py` com init lazy.
4. Se a tool precisa ser escopada por usuário/estoque, usar o `ContextVar` de
   `tools/postgres/context.py` — nunca adicionar `user_id`/`stock_id` ao schema da tool.
5. Registrar a tool no agente correspondente em `agents/nodes/`.
6. Atualizar a tabela de estrutura no README.md.

## Skills por biblioteca

`.agents/skills/` guarda convenções e pegadinhas específicas de cada lib/serviço externo usada no
projeto (pydantic, fastapi, mongo, langchain, spoonacular — um arquivo por lib, regra + exemplo do
que fazer e do que não fazer).
`dependencies.md`, `responses.md`, `streaming.md`, `path-operations.md` e `other-tools.md` são
material de referência do skill oficial do FastAPI, linkados a partir de `fastapi.md`. São achados
reais deste repo ou do assessor-ai (repo irmão, mesmo stack de Mongo/LangChain — sinalizado quando o
achado é de lá), não tutorial genérico. Consulte antes de escrever código novo que toque uma dessas
libs; adicione uma entrada nova quando encontrar uma pegadinha não óbvia que provavelmente vai se
repetir.

## Próximos passos

Refatoração de estrutura e roadmap de implementação (MCP, A2A, observabilidade, etc.) estão em
[TODO.md](TODO.md) — confira antes de começar qualquer trabalho novo, pra não duplicar decisão já
tomada ou já descartada lá.

## Claude Code

Para instruções específicas de como o Claude Code deve operar neste repo, ver [CLAUDE.md](CLAUDE.md).
