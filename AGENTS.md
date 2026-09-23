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
grafo e persistir histórico vive em `frigus_ai.services.chat_service`, compartilhada por todas as
interfaces (`tui`, `api`, A2A e MCP). Detalhes de arquitetura, fluxo de agentes e tools estão no
[README.md](README.md) — leia-o antes de mexer em `src/frigus_ai/graph/`.

## Requisitos da disciplina

Baseado no enunciado do trabalho ("mínimo para 7,0" + extra). Cada item marca o que já está feito
neste repo e onde. Antes de reportar algo como pendente, confira o código — este checklist pode
ficar desatualizado.

**A ordem de ataque do que falta (P0/P1/P2) fica em
`.agents/notes/pending/requisitos-disciplina/arquivos.md`** — esta tabela só diz onde está cada
coisa; a nota diz o que fazer primeiro.

| Requisito | Status | Onde |
|---|---|---|
| API FastAPI/Flask | ⚠️ Parcial | `src/frigus_ai/api/` — health, chats, keys, MCP e A2A, com autenticação/rate limit condicionais. `GET /chats` tipado (`ChatSummaryResponse`) e `DELETE /chats/{id}` checa ownership (403 pra não-dono). Validação de ownership em `POST /a2a`. Falta versionamento |
| Multiagente, mínimo 5 agentes | ✅ Feito | 11 nós no grafo: guardrail entrada/saída, router, estoque, compras, receitas, faq, financeiro, visão, orquestrador, juiz (`graph/names.py`) |
| LangChain para criação dos agentes | ✅ Feito | `graph/agents.py` |
| LangGraph para orquestração | ✅ Feito | `graph/builder.py` |
| Controle de sessões por usuário | ⚠️ Parcial | `thread_id=session_id` no `MongoDBSaver` + histórico em Mongo. Ownership checado em `send_message`, `get_messages`, `/stream`, `DELETE` e no A2A (`contextId` valida dono antes de entrar na sessão) |
| Memória de longo prazo | ⚠️ Parcial | Fatos estruturados (`alergias`/`preferencias`/`restricoes`/`habitos`) persistidos em Mongo (`user_fatos`, `repositories/fatos_repository.py`), extraídos automaticamente do chat e expostos via `GET/PUT /profile`. Perfil comportamental em texto livre (`user_profiles`) foi removido — nunca era lido pelo grafo, e a decisão foi ir direto para fatos estruturados em vez de reconsertar o texto livre. `fatos` em si também ainda não é lido de volta pelo prompt do chat, só usado na extração/merge |
| MCP | ⚠️ Parcial | `src/frigus_ai/mcp.py` expõe as tools com autenticação por `X-API-Key`; falta validação externa ponta a ponta |
| A2A | ⚠️ Parcial | Superfície única e consolidada em `src/frigus_ai/api/routes/a2a.py` (contrato manual, com auth real por `X-API-Key`). A integração alternativa via `a2a-sdk` foi removida: o dispatcher da SDK sempre responde HTTP 200 e embute erro no corpo JSON-RPC, perdendo o 429/401 de transporte que o contrato manual já entrega |
| RAG com fonte externa indicada | ✅ Feito | `graph/tools/faq/` — Qdrant sobre `data/pdf/Frigus-Documentacao.pdf` (fonte local, categoria explicitamente aceita pelo enunciado) |
| Agente juiz (mitigação de alucinação) | ✅ Feito | `graph/nodes/juiz.py` — audita grounding/relevância/completude, até 2 retentativas |
| Guardrail | ✅ Feito | `graph/guardrail/` — entrada (PII via `privacy.py`, regex de ataque, classificador com cache no Redis) e saída |
| Observabilidade/SRE — custo estimado (100 e 1000 usuários/semana) | ⚠️ Parcial | `evals/sre_report.py` calcula a estimativa a partir do custo médio por turno observado; premissa de volume (`MENSAGENS_POR_USUARIO_SEMANA`) é placeholder até haver dado real de uso |
| Observabilidade/SRE — latência interagentes e tempo total de resposta | ✅ Feito | Prometheus mede HTTP, grafo, nodes, tools e LLM; LangSmith complementa os traces individuais |
| Observabilidade/SRE — índice de erros | ⚠️ Parcial | `evals/sre_report.py` define fórmula (`error` / total de `frigus_graph_runs_total`) e relatório; falta rodar contra scrape real acumulado (não só o processo atual) |
| Observabilidade/SRE — custo/ROI | ⚠️ Parcial | `evals/sre_report.py` calcula ROI, mas `VALOR_POR_RESOLUCAO_USD` é placeholder — falta valor de negócio real pra o número fazer sentido |
| Observabilidade/SRE — custo por resolução | ⚠️ Parcial | `evals/sre_report.py` define resolução = `frigus_graph_runs_total{outcome="success"}` e calcula custo/resolução a partir da tabela de preços por modelo |
| Desenho de arquitetura de alto nível | ✅ Feito | README.md — diagrama Mermaid + `assets/diagrama-agentes.png` |
| Extra: Redis com fila ou ranking | ✅ Feito | `infra/redis/ranking.py` — ranking de produtos mais desperdiçados por `ZINCRBY`/`ZREVRANGE`, alimentado em `discard_product` e exposto como tool (`ranking_desperdicio`, domínio financeiro) |
| Extra: Neo4j | ⚠️ Parcial | `neomodel` (OGM) no `pyproject.toml`, conexão lazy em `infra/neo4j/connection.py`, models `User`/`Ingredient`/`Recipe` com relações (`PREFERS`/`DISLIKES`/`ALLERGIC_TO`/`REQUIRES`/`SIMILAR_TO`). Tools de preferências (`graph/tools/preferencias/`, CRUD + traversal `sugerir_receitas_compativeis`) agora expostas ao LLM dentro do toolset de receitas (`RECEITAS_TOOLS`) — antes existiam mas não estavam ligadas a nenhum node. `definir_preferencia` cria o node do usuário no grafo na primeira preferência (não há sync automático Postgres → Neo4j de usuário). Falta: sync automático de `products`/`recipes` do Postgres pro grafo (nunca existiu script pra isso, só seed manual em `infra/neo4j/cql/`) e mapear fatos (`user_fatos`, ver memória incremental) pras relações do grafo |
| Extra: visão computacional (foto da geladeira) | ⚠️ Parcial | `POST /stock/foto` (`api/routes/stock.py`) + node `visao_node` (`graph/nodes/visao.py`, `with_structured_output` no Gemini Flash, bypassa o roteador via `imagem_b64` no estado). Só descreve o que reconheceu, em linguagem natural — não escreve no estoque; usuário confirma via `POST /stock/items` numa mensagem separada. Limite de 8MB no upload. Falta: `thread_id` da foto some depois de uso (checkpoint com a imagem em base64 fica órfão no Mongo pra sempre, ver nota abaixo) |
| Extra: complexidade do projeto | Em andamento | 6 domínios de negócio + guardrail duplo + juiz + RAG + integrações MCP/A2A + ranking Redis + Neo4j + visão já são acima da média |

### Checklist por matéria/entrega

| Área | Feito e comprovado | Pendente para fechar |
|---|---|---|
| Sistemas Multiagentes | Grafo LangGraph, 5+ especialistas, router, guardrails e juiz com retentativas | Avaliação reproduzível de qualidade e grounding |
| API e integrações | FastAPI, health, chats, autenticação condicional, MCP e A2A manual (superfície única); ownership checado em `send_message`, `get_messages`, `/stream` e `DELETE /chats/{id}`; `GET /chats` tipado | Versionamento |
| Persistência | PostgreSQL, MongoDB, Redis e Qdrant lazy; histórico, fatos estruturados e checkpoint; todos os domínios (`receitas`, `financeiro`, `estoque`, `compras`) em SQLAlchemy + `@transacional`; pool `psycopg2` removido | IDs seguros contra concorrência e validação real com Docker |
| MCP | Tools em `src/frigus_ai/mcp.py`, contexto de usuário/estoque e testes MCP | Teste externo/ponta a ponta e documentação de cliente |
| A2A | Contrato manual único em `api/routes/a2a.py`, com autenticação real por `X-API-Key` (`api/auth.py`); `a2a-sdk` removido do código (decisão registrada abaixo em "Estrutura") | Persistir sessão A2A além do `contextId` in-memory, se necessário |
| Observabilidade/SRE | `/metrics`, métricas HTTP/grafo/node/tool/LLM, Prometheus e dashboard Grafana; `evals/sre_report.py` calcula custo, índice de erros, custo/resolução e ROI a partir dos contadores | Validar contra scrape real acumulado (não só um processo local) e substituir os placeholders (volume de mensagens/usuário, valor por resolução) por dado real |
| Avaliação da disciplina | Métricas de runtime movidas pra `observability/`; `evals/` agora só tem `sre_report.py` (custo/erro/ROI) e o harness de cenários (`evals/scenarios.py` + `run_scenarios.py`) | Rodar o harness contra infra viva (Docker + API keys) e produzir o relatório final |
| Extras | RAG, arquitetura documentados, ranking de desperdício em Redis (`infra/redis/ranking.py`), Neo4j conectado (models + tools de preferências + traversal `sugerir_receitas_compativeis`) e visão computacional (`POST /stock/foto`, `graph/nodes/visao.py`) | Sync automático Postgres → Neo4j (produtos/receitas); limpar `imagem_b64` do checkpoint da thread de foto |

**Importante:** a escola não paga API de IA generativa — por isso o projeto já usa só providers com
tier gratuito viável (Gemini, Groq) e Claude/Anthropic como opcional (`ANTHROPIC_API_KEY` tem
default vazio em `src/frigus_ai/settings.py`, então o projeto roda sem ela).

## Stack

- Python 3.13+, gerenciado com `uv` (`uv venv`, `uv sync`, `uv add <pkg>`)
- LangChain 1.2 / LangGraph 1.1 para orquestração de agentes
- LLMs: Gemini (`gemini-2.5-flash`), Groq (`llama-3.3-70b-versatile`, `qwen-2.5-pro`), Claude
  (`claude-haiku-4-5`, `claude-sonnet-4-6`) e OpenRouter (`z-ai/glm-5.2:free`) mapeados em
  `src/frigus_ai/models.py`. Provider sem API key configurada faz `build_llm` devolver `None` e fica
  fora da cadeia de fallback — só Gemini e Groq são obrigatórios
- PostgreSQL (via Docker) para estoque/compras/receitas/financeiro, acessado via SQLAlchemy
  (`infra/postgres/connection.py`, `@transacional`; schema `dataload`, DDL fornecido em
  `data/sql/schema.sql`)
- MongoDB para histórico de conversa (`repositories/chat_repository.py`), fatos estruturados do
  usuário (`repositories/fatos_repository.py`, coleção `user_fatos`) e checkpoint do LangGraph
  (`MongoDBSaver`, coleções `graph_checkpoints`/`graph_checkpoint_writes`)
- Qdrant para RAG do FAQ sobre `data/pdf/Frigus-Documentacao.pdf` (`graph/tools/faq/`)
- Redis para rate limit de chat e ranking de desperdício (`src/frigus_ai/infra/redis/`)
- Prometheus/LangSmith para observabilidade operacional; avaliações offline e relatórios da
  disciplina devem ficar em `evals/`, separados do runtime
- `pytest` (`tests/`, espelhando a estrutura do pacote) + `ruff` (lint) + CI no GitHub Actions
  (`.github/workflows/ci.yml`)

## Estrutura

```text
src/frigus_ai/          o "cérebro" do assistente, pacote instalável (hatchling, layout src/)
├── graph/               tudo do LangGraph
│   ├── state.py         Estado + EntradaGrafo/SaidaGrafo + os *Update de cada nó + AsyncNode[R]
│   ├── names.py         nomes dos nós. Fora de nodes/ de propósito: state.py importa daqui e, de
│   │                     dentro do pacote, o __init__ fecharia ciclo de import
│   ├── builder.py       monta e compila o grafo (+ checkpointer Mongo)
│   ├── llm.py           builders de LLM   |   agents.py  agentes compilados (create_agent)
│   ├── prompts/         só .md + __init__.py — load_prompt()/load_sections() montam o system_prompt
│   │                     a partir de frontmatter (metadados) + seções `## NOME` do corpo
│   ├── nodes/           um arquivo por nó + contexto.py (responder/perguntar/poda do histórico)
│   ├── guardrail/       subsistema próprio: entrada/saida (nós), padroes, schemas, cache
│   └── tools/           tools do LLM por domínio: estoque, compras, receitas, financeiro, faq,
│                         spoonacular — cada uma com schemas.py + repo.py
├── repositories/        persistência: Postgres via SQLAlchemy (@transacional) e Mongo
├── services/            casos de uso (chat_service, user_service, api_key_service, runner)
├── infra/               conexões lazy: postgres (pool + engine + models), mongo, redis, qdrant,
│                         neo4j, spoonacular
├── api/                 app.py, routes, schemas, auth, middleware e handlers da API FastAPI
├── observability/       métricas Prometheus de runtime (metrics.py, metrics_callback.py)
├── evals/               avaliação offline: sre_report.py (custo/erro/ROI) e o harness de cenários
├── privacy.py           PII: anonimizar/desanonimizar/redigir. Neutro — guardrail, repository e
│                         service usam; por isso não mora dentro do guardrail
└── tui/                 app.py (Textual) + display.py + app.tcss — interface interativa

data/                   pdf/Frigus-Documentacao.pdf (RAG) + sql/schema.sql (DDL fornecido)
prometheus/ grafana/    scrape config, datasource e dashboard (8 painéis)
main.py                 dispatcher fino — `python main.py <interface>` (`tui` [default] ou `api`)
```

Padrão de cada domínio de tool: `schemas.py` (Pydantic) + `repo.py` (as tools em si), com
`connection.py`/`context.py`/`helpers.py` compartilhados em `infra/postgres/`. Siga esse padrão para
qualquer tool nova (redis, qdrant, etc).

Nenhuma interface (`api/`, `tui/`) deve chamar `frigus_ai.graph.builder` ou `frigus_ai.infra.*`
diretamente — sempre via `frigus_ai.services.chat_service`. É esse limite que permite API/TUI
existirem sem duplicar a lógica de montar estado, invocar o grafo e persistir histórico.
`src/frigus_ai/api/routes/chats.py` segue essa regra. Identidade real já não depende de
`DEMO_USER_ID` fixo — `api/auth.py:resolver_usuario` resolve por `X-API-Key` ou cria/reaproveita o
usuário local único quando `API_KEY_AUTH_ENABLED=false` (modo local/demo).

`interfaces/terminal/` foi removido — a TUI (Textual) é a única interface interativa agora.
`src/frigus_ai/mcp.py` existe; o A2A vive só em `api/routes/a2a.py` (ver docstring do arquivo).
Havia uma segunda implementação em `src/frigus_ai/a2a.py`, via `a2a-sdk` — removida porque o
dispatcher JSON-RPC da SDK captura qualquer exceção e sempre responde HTTP 200 com o erro
embutido no corpo, perdendo o 429 (rate limit) e 401 (auth) de transporte que o contrato manual
já entrega e testa. Os tipos da SDK (`AgentCard` etc.) também são mensagens protobuf, não Pydantic
— reusá-los exigiria conversão proto→dict a cada resposta sem ganhar nada sobre o schema Pydantic
já escrito em `schemas/a2a.py`. Se o card um dia precisar de streaming/tasks de verdade, revisitar.
O MCP e o A2A ainda devem ser tratados como integrações parcialmente concluídas até que seus
contratos externos, autenticação e testes de ponta a ponta estejam fechados.

`src/frigus_ai/observability/metrics.py` e `metrics_callback.py` são observabilidade de runtime
(Prometheus, importados por todos os nós do grafo) — não devem morar em `evals/`. A pasta `evals/`
contém só avaliação offline: `sre_report.py` (custo/erro/ROI, lê os contadores do `observability/`
via HTTP do Prometheus) e o harness de cenários (datasets, execução de casos, agregação e
relatórios de custo, erro, latência, ROI e custo por resolução). Não misturar prompts/respostas
reais com métricas Prometheus nem commitar segredos.

## Convenções

- **Não alterar nem apagar código sem solicitação explícita do usuário.** Mudanças de código,
  configuração ou documentação só devem ser feitas quando fizerem parte do pedido atual. Arquivos
  só podem ser apagados com permissão prévia específica; prefira adaptar ou deixar o legado fora do
  caminho de execução até essa autorização.
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
  o schema e as tools atrás da entrada dela. Caso já barrado por essa regra: resolução de produto
  por código de barras (não existe coluna de código de barras em `data/sql/schema.sql`, e a leitura
  de NF-e é stub).

- Código de domínio (nomes de função, variáveis, docstrings de tool, mensagens ao usuário) é em
  **português**; nomes de classes/tipos de infraestrutura (`Settings`, `Model`, `Route`) em inglês.
  Siga o idioma já usado no arquivo que você está editando.
- Enums de domínio usam `StrEnum` (ver `graph/guardrail/schemas.py:Categoria`,
  `schemas/models.py:Role`). **Exceção:** `graph/state.py:Route` e `graph/names.py:NodeLiteral` são
  `Literal` + classe de constantes (não `StrEnum`) — valores guardados em `Estado` (checkpointado
  pelo `MongoDBSaver`) precisam ser `str` puro pro msgpack, sem allowlist extra
  (`LANGGRAPH_ALLOWED_MSGPACK_MODULES` foi removido de `graph/builder.py` por causa disso).
- Conexões com banco (Postgres, Mongo) são **lazy** — inicializadas só na primeira operação, nunca
  no import do módulo. Mantenha esse padrão para novas integrações (Redis, Qdrant, MCP, A2A).
- Tools retornam a classe `Response` (`graph/tools/response.py`) para padronizar sucesso/erro.
- **Tools do LLM nunca recebem `user_id`/`stock_id` como argumento.** Args de tool são escolhidos
  pelo LLM via tool-calling — qualquer dado de escopo/permissão não pode vir por ali. O padrão é um
  `contextvars.ContextVar` setado uma vez por request (`infra/postgres/context.py:session_context`,
  chamado em `services/runner.py:executar`) e lido dentro da tool. Ver uso em
  `graph/tools/{estoque,compras,receitas,financeiro}/repo.py`.
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
  `tests/graph/guardrail/test_entrada.py`, que cobre só os caminhos determinísticos).
- Pegadinha nova de lib vira entrada em `.agents/skills/<lib>.md`.

## Padrões de organização e clean code

- **Single responsibility por nó de agente.** `graph/nodes/` (execução) fica separado de
  `graph/prompts/` (conteúdo/persona) — mudar o texto de um prompt nunca deveria exigir tocar na
  lógica de roteamento do grafo, e vice-versa.
- **Contrato de retorno único.** Tools não retornam dict cru nem deixam exception vazar para o
  agente — usam `Response` (`graph/tools/response.py`). Ao criar tool nova, reusar essa classe.
- **Config centralizada.** Uma única fonte de env vars (`src/frigus_ai/settings.py`,
  `pydantic-settings`) e um único enum fechado de modelos/providers
  (`src/frigus_ai/models.py:Model`/`PROVIDER_MAP`). Não ler `os.environ` direto em outros módulos.
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

1. Criar `graph/tools/<domínio>/schemas.py` com os modelos Pydantic de entrada/saída.
2. Criar `graph/tools/<domínio>/repo.py` com as funções decoradas como tool (ver
   `logging.py:Logging.log_tool`).
3. Se for um serviço externo com estado de conexão, criar `connection.py` com init lazy.
4. Se a tool precisa ser escopada por usuário/estoque, usar o `ContextVar` de
   `infra/postgres/context.py` — nunca adicionar `user_id`/`stock_id` ao schema da tool.
5. Registrar a tool no agente correspondente em `graph/agents.py`.
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

Para o refactor de alinhamento com o assessor-ai, a fonte prioritária de continuidade, decisões e
pendências é `.agents/notes/`, que fica no mesmo nível de `.agents/skills/`. Leia primeiro
`.agents/notes/README.md`, depois as notas em `implemented/` e `pending/`.

Novas migrações e alterações relevantes devem ser documentadas em
`.agents/notes/<implemented|pending>/<titulo-da-mudanca>/arquivos.md`, com os arquivos tocados,
a ideia da mudança, decisões e pendências. Quando uma pendência for concluída, atualize a nota
correspondente e mova-a para `implemented/`, sem apagar histórico.

## Claude Code

Para instruções específicas de como o Claude Code deve operar neste repo, ver [CLAUDE.md](CLAUDE.md).
