# AGENTS.md

Contexto do projeto **Frigus.AI** para agentes de IA (Claude Code, Copilot, etc.) trabalhando neste
repositório.

## O que é

Assistente conversacional multi-agente do app **Frigus** (gestão de alimentos em geladeira/freezer/
despensa, compras, receitas e finanças domésticas). Construído com LangChain + LangGraph, RAG
(Qdrant) e um agente juiz (LLM-as-judge) para mitigar alucinação. Também é o **projeto da disciplina
de Sistemas Multiagentes** — ver seção "Requisitos da disciplina" abaixo para o que precisa ser
entregue e o que já está feito.

`main.py` (em `src/frigus_ai/`) é um dispatcher fino (`python -m frigus_ai.main <interface>`) — a lógica de montar estado, invocar o
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
| API FastAPI/Flask | ✅ | `api/` — rotas de negócio em `/v1`, health, keys, MCP e A2A; auth e rate limit condicionais (fastapi-guard); ownership checado em chats e no A2A |
| Multiagente, mínimo 5 agentes | ✅ | 12 nós no grafo (`graph/names.py`): guardrail entrada/saída, router, estoque, compras, receitas, faq, financeiro, assessor (A2A), visão, orquestrador, juiz |
| LangChain / LangGraph | ✅ | `graph/agents.py` / `graph/builder.py` |
| Controle de sessões por usuário | ✅ | `thread_id=session_id` no `MongoDBSaver` + histórico em Mongo; validado com bancos reais (`observability/RELATORIO.md`) |
| Memória de longo prazo | ✅ | Fatos estruturados em Mongo (`user_fatos`, `GET/PUT /v1/profile`) + resumo por chat com embedding no Qdrant; voltam pro prompt via `Runtime.context` (`services/runner.py:_carregar_contexto`); reconciliador no lifespan refaz o que falhou |
| MCP | ✅ | `api/mcp.py` em `/mcp`, 20 tools, identidade por `X-API-Key`; cliente de teste em `scripts/mcp_client.py` |
| A2A | ✅ | Contrato manual único em `api/routes/a2a.py` (ver "Estrutura" sobre o `a2a-sdk` removido) |
| RAG com fonte externa | ✅ | `graph/tools/faq/` — Qdrant sobre `data/pdf/Frigus-Documentacao.pdf` |
| Agente juiz | ✅ | `graph/nodes/juiz.py` — audita contra o retorno real das tools, até 2 retentativas pelo orquestrador; falha na avaliação vira `INDISPONIVEL`, não `APROVADO`. JeV como avaliador quando o gateway está configurado |
| Guardrail | ✅ | `graph/guardrail/` — entrada (PII, regex, classificador com cache Redis; JeV com gateway) e saída; fallback Gemini → Groq → Luna (`graph/llm.py:estruturado`) |
| Observabilidade/SRE | ✅ | Prometheus (HTTP, grafo, nodes, tools, LLM), SLO/SLI e alertas em `observability/prometheus/rules.yml`, custo/erro/ROI/custo por resolução em `telemetry/evals/sre_report.py`. Números medidos e ressalvas (SLO de 8s não bate por latência do LLM; sem SLA nem Alertmanager): `observability/RELATORIO.md` |
| Desenho de arquitetura | ✅ | README.md — seção "Arquitetura" (Mermaid) + `assets/diagrama-agentes.png` |
| Extra: Redis fila/ranking | ✅ | `infra/redis/ranking.py` — ranking de desperdício, tool `ranking_desperdicio` |
| Extra: Neo4j | ✅ | `infra/neo4j/`, `repositories/grafo_receitas_repository.py` — sync Postgres → grafo no `lifespan` (214 receitas no Aura, conferido em 2026-10-29), `GET /v1/recipes/suggestions` e tool `sugerir_receitas_compativeis`; cai no cruzamento SQL se o Neo4j falhar |
| Extra: visão computacional | ✅ | `POST /stock/foto` + `graph/nodes/visao.py`; foto vai por `context=` (`ContextoPrompt.imagem_b64`), nunca pelo estado; só descreve, não escreve no estoque; limite de 8MB (`api/uploads.py`) |
| Extra: complexidade | ✅ | 6 domínios + guardrail duplo + juiz + RAG + MCP/A2A + Redis + Neo4j + visão |

**Importante:** a escola não paga API de IA generativa. Desde 2026-10-23 o chat roda na GPT-6 Luna pelo
Vercel AI Gateway (créditos pagos do bolso por um integrante, não pela escola: ~US$ 0,002 por turno), porque os planos gratuitos do Gemini
(20 requisições/dia) e do Groq (8 mil tokens/minuto) não aguentam um turno do grafo. Sem
`LLM__GATEWAY__API_KEY` o projeto ainda roda, só no Groq (lento, com 429) e sem JeV. Claude/Anthropic
segue opcional (`ANTHROPIC_API_KEY` tem default vazio em `src/frigus_ai/settings/`).

## Stack

- Python 3.13+, gerenciado com `uv` (`uv venv`, `uv sync`, `uv add <pkg>`)
- LangChain 1.2 / LangGraph 1.1 para orquestração de agentes
- LLMs: GPT-6 Luna (`openai/gpt-6-luna`, pelo Vercel AI Gateway, `reasoning_effort="low"`) em todas as
  cadeias de chat e na visão, Groq (`openai/gpt-oss-120b`) e OpenRouter (`qwen/qwen3.8-27b:free`) de
  reserva, Claude (`claude-haiku-4-5`, `claude-sonnet-4-6`) opcional e Gemini só para embeddings
  (`gemini-embedding-001`). O enum `Model` fica em `settings/llm.py`, cada provider
  tem seu bloco em `LLMSettings` (`gemini`, `groq`, `claude`, `gateway`, `openrouter`: chave, URL,
  timeout e tentativas) e `infra/llm/` (`registry.py`, `builder.py`) constrói o modelo. Provider sem
  API key faz `build_llm` devolver `None` e fica fora das cadeias de fallback — só Gemini e Groq são
  obrigatórios.
- JeV (TypeSafe), pela Decisions API do Vercel AI Gateway (`infra/llm/jev/`): decide sem gerar texto
  (predicado, escolha e nota, com probabilidade). Com `LLM__GATEWAY__API_KEY`, é ele quem classifica
  o guardrail de entrada, escolhe os especialistas no roteador e avalia a resposta no juiz; se
  falhar, o LLM assume. Ver `.agents/skills/jev.md`.
- PostgreSQL (via Docker) para estoque/compras/receitas/financeiro, acessado via SQLAlchemy
  (`infra/postgres/connection.py`, `@transacional`; banco real no Supabase, schema
  `public` — enums gravados como código em inglês e traduzidos por `models/base.py:Rotulo`;
  `data/sql/schema.sql` espelha esse schema e inicializa o Postgres local do docker-compose)
- MongoDB para histórico de conversa (`repositories/chat_repository.py`), fatos estruturados do
  usuário (`repositories/fatos_repository.py`, coleção `user_fatos`) e checkpoint do LangGraph
  (`MongoDBSaver`, coleções `graph_checkpoints`/`graph_checkpoint_writes`)
- Qdrant para RAG do FAQ sobre `data/pdf/Frigus-Documentacao.pdf` (`graph/tools/faq/`)
- Redis para rate limit de chat e ranking de desperdício (`src/frigus_ai/infra/redis/`)
- Prometheus/LangSmith para observabilidade operacional; avaliações offline e relatórios da
  disciplina devem ficar em `telemetry/evals/`, separados do runtime
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
│   │                     a partir das seções `## NOME` dos .md (blocos comuns em sistema.md)
│   ├── nodes/           um arquivo por nó + contexto.py (responder/responder_com_evidencias/perguntar/poda do histórico)
│   ├── guardrail/       subsistema próprio: entrada/saida (nós), padroes, schemas, cache
│   └── tools/           tools do LLM por domínio: estoque, compras, receitas, financeiro, faq,
│                         spoonacular — cada uma com schemas.py + repo.py
├── domain/              modelos de domínio (models.py: Role/ChatMessage/Fatos/Resumo), tipos de ID e novo_chat_id
├── repositories/        persistência: Postgres via SQLAlchemy (@transacional) e Mongo
├── services/            casos de uso (chat_service, user_service, auth_service, runner); stock/shopping/recipe_service atrás das rotas v1
├── infra/               conexões lazy: postgres (engine + models), mongo, redis, qdrant, neo4j,
│                         firebase, spoonacular, assessor (A2A) e llm/ (builder, registry e jev/)
├── api/                 app.py (create_app), deps.py (Depends), routes/{v1,auth,health,metrics,a2a}, auth/, mcp.py, middleware/{request_id,metrics,security}, errors/ (handlers + ErrorResponse)
├── (infra/logging/)     setup.py (logger colorido + request_id) e decorators.py (log_tool/log_classe); `Logging` é a fachada
├── telemetry/           métricas Prometheus de runtime (metrics.py, metrics_callback.py) e evals/ (avaliação
│                         offline: sre_report.py custo/erro/ROI e o harness de cenários)
├── (domain/privacy.py)  PII: anonimizar/desanonimizar/redigir. Neutro — guardrail, repository e
│                         service usam; por isso não mora dentro do guardrail
├── main.py              dispatcher fino — `python -m frigus_ai.main <interface>` (`tui` [default] ou `api`)
└── tui/                 app.py (Textual) + display.py + app.tcss — interface interativa

data/                   pdf/Frigus-Documentacao.pdf (RAG) + sql/schema.sql (espelho do DDL do Supabase)
observability/          prometheus/ (scrape config, regras de SLO) — profile `observability` do compose (`just obs`);
                        RELATORIO.md (cenários, SRE e sessões contra a infra real)
scripts/                run.sh (sobe o Docker e a app) e prometheus_token.py (token do /metrics → Prometheus)
web/                    painel React (Vite): chat com timeline de execução, perfil e /metrics

```

Padrão de cada domínio de tool: `schemas.py` (Pydantic) + `repo.py` (as tools em si), com
`connection.py`/`context.py`/`helpers.py` compartilhados em `infra/postgres/`. Siga esse padrão para
qualquer tool nova (redis, qdrant, etc).

Nenhuma interface (`api/`, `tui/`) deve chamar `frigus_ai.graph.builder` ou `frigus_ai.infra.*`
diretamente — sempre via `frigus_ai.services.chat_service`. É esse limite que permite API/TUI
existirem sem duplicar a lógica de montar estado, invocar o grafo e persistir histórico.
`src/frigus_ai/api/routes/v1/chats.py` segue essa regra. Identidade real já não depende de
`DEMO_USER_ID` fixo — `api/auth/dependencies.py:resolver_usuario` resolve pelo Bearer do Firebase (login
do app Frigus) ou por `X-API-Key`, ou cria/reaproveita o usuário local único quando
`API__KEY_AUTH_ENABLED=false` (modo local/demo).

`interfaces/terminal/` foi removido — a TUI (Textual) é a única interface interativa.
O A2A vive só em `api/routes/a2a.py` (contrato manual). A integração via `a2a-sdk` foi removida: o
dispatcher JSON-RPC da SDK sempre responde HTTP 200 com o erro no corpo, perdendo o 429/401 de
transporte, e os tipos da SDK são protobuf, não Pydantic. Revisitar só se o card precisar de
streaming/tasks de verdade.

`src/frigus_ai/telemetry/metrics.py` e `metrics_callback.py` são observabilidade de runtime
(Prometheus, importados por todos os nós do grafo) — não devem morar em `telemetry/evals/`. A subpasta `telemetry/evals/`
contém só avaliação offline: `sre_report.py` (custo/erro/ROI, lê os contadores do `telemetry/`
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
  shadowando o `Role` do schema em `schemas/chat.py`); o rate limit funcionava mas a
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
  `domain/models.py:Role`). **Exceção:** `graph/state.py:Route` e `graph/names.py:NodeLiteral` são
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
- **Comentário só explica um porquê que o código não mostra** (pegadinha, restrição externa). Nada
  que repita o código, conte histórico ("antes era X") ou narre a mudança. O que sobrar vai em
  linha própria acima do item, separado por linha em branco do bloco anterior — nunca longo no fim
  da linha nem colado em várias linhas de código. Vale pra campo de classe, função e dict.
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
- **Config centralizada.** Uma única fonte de env vars (`src/frigus_ai/settings/`,
  `pydantic-settings`) e um único enum fechado de modelos/providers
  (`settings/llm.py:Model` e `infra/llm/registry.py:PROVIDER_MAP`). Não ler `os.environ` direto em outros módulos.
  Variáveis de provider são aninhadas: `LLM__GROQ__API_KEY`, `LLM__GATEWAY__TIMEOUT_S`. Renomear uma
  variável exige atualizar o ambiente de deploy: com `extra="ignore"`, o nome antigo é descartado sem erro.
- **Ciclo de retentativa do Juiz é explícito no grafo**, não escondido em loop Python — ver
  `decidir_apos_juiz` em `graph/builder.py`. A retentativa volta só ao orquestrador (repetir
  especialistas regravaria estoque e lista de compras). Novo especialista: registre-o em
  `NO_POR_DOMINIO`, crie o nó com `@especialista` (ou `especialista_com_agente`) e ele passa pelo
  Orquestrador e pelo Juiz antes do Guardrail de Saída. Roteador e orquestrador estão descritos em
  `graph/prompts/router.md` e `orquestrador.md`. Novo especialista também entra como pergunta do
  roteador JeV (`DESCRICAO_ESPECIALISTA` em `graph/nodes/router.py`).

## Comandos

```bash
uv venv && uv sync   # instalar dependências
just run             # sobe a TUI (sobe Postgres/Mongo/Redis/Qdrant via Docker automaticamente)
just run api          # sobe a API (FastAPI/uvicorn, localhost:8000)
just web              # API em modo local (`just api-local`: sem auth, usuário com estoque) + painel web (localhost:5173), abre direto no chat
just test            # suíte de testes (não precisa de .env nem banco)
just check           # lint (roda no CI em push/PR pra main); `just fix` aplica o que dá
just obs             # Prometheus (9090), já com o token do /metrics do .env
```

`just run` chama o console script `frigus-ai` (`[project.scripts]`), que é o mesmo
`python -m frigus_ai.main tui`. Ver `justfile` para as demais receitas.

## Ao adicionar uma tool nova

1. Criar `graph/tools/<domínio>/schemas.py` com os modelos Pydantic de entrada/saída.
2. Criar `graph/tools/<domínio>/repo.py` com as funções decoradas como tool (ver
   `infra/logging/decorators.py:log_tool`, via `Logging.log_tool`).
3. Se for um serviço externo com estado de conexão, criar `connection.py` com init lazy.
4. Se a tool precisa ser escopada por usuário/estoque, usar o `ContextVar` de
   `infra/postgres/context.py` — nunca adicionar `user_id`/`stock_id` ao schema da tool.
5. Registrar a tool no agente correspondente em `graph/agents.py`.
6. Atualizar a tabela de estrutura no README.md.

## Skills por biblioteca

`.agents/skills/` guarda convenções e pegadinhas específicas de cada lib/serviço externo usada no
projeto (pydantic, fastapi, mongo, langchain, jev, mcp, spoonacular — um arquivo por lib, regra + exemplo do
que fazer e do que não fazer).
São achados reais deste repo ou do assessor-ai (repo irmão, mesmo stack de Mongo/LangChain —
sinalizado quando o achado é de lá), não tutorial genérico. Consulte antes de escrever código novo que toque uma dessas
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
