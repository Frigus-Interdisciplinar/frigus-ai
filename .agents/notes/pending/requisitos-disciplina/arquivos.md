# Requisitos da disciplina — o que falta

Conferido contra o código em `fix/broken-tests` (suíte: 232 passed) em 2026-09-23.
Antes de reportar item como pendente, confira o código: este checklist envelhece.

## Placar

| Requisito | Status | Onde / o que falta |
| --- | --- | --- |
| API FastAPI/Flask | ⚠️ | `api/` com health, chats, keys, MCP e A2A. `GET /chats` tipado (`ChatSummaryResponse`), `DELETE /chats/{id}` com ownership (403). Falta: versionamento |
| Multiagente (mín. 5 agentes) | ✅ | 10 nós (`graph/names.py`) |
| LangChain pra criar agentes | ✅ | `graph/agents.py` |
| LangGraph pra orquestrar | ✅ | `graph/builder.py`, com `input_schema`/`output_schema` e contrato `AsyncNode[R]` |
| Sessões por usuário | ⚠️ | `thread_id=session_id` no `MongoDBSaver` + histórico no Mongo. Ownership fechado em `send_message`, `get_messages`, `/stream`, `DELETE` e no A2A (`contextId` valida dono) |
| Memória de longo prazo | ⚠️ | Fatos estruturados (`alergias`/`preferencias`/`restricoes`/`habitos`) em Mongo (`user_fatos`), extraídos automaticamente a cada 10 mensagens; `restricoes` normalizado pra vocabulário canônico. Perfil comportamental em texto livre (`user_profiles`) foi removido — nunca era lido pelo grafo. `fatos` ainda não é injetado de volta no prompt do chat |
| MCP | ⚠️ | `mcp.py` expõe as tools com `X-API-Key`. Falta validação externa ponta a ponta |
| A2A | ✅ | Superfície única em `api/routes/a2a.py` (contrato manual, `a2a-sdk` removido — decisão em `AGENTS.md`) |
| RAG com fonte externa | ✅ | `graph/tools/faq/` — Qdrant sobre `data/pdf/Frigus-Documentacao.pdf` |
| Agente juiz | ✅ | `graph/nodes/juiz.py` — grounding/relevância, até 2 retentativas |
| Guardrail | ✅ | `graph/guardrail/` — entrada (PII + ataque + classificador com cache) e saída |
| SRE: latência interagentes | ✅ | Prometheus mede HTTP, grafo, node, tool e LLM; dashboard Grafana com 8 painéis |
| SRE: custo 100 e 1000 usuários/semana | ⚠️ | `evals/sre_report.py` estima a partir do custo médio por turno; volume/usuário é placeholder |
| SRE: índice de erros | ⚠️ | `evals/sre_report.py` define fórmula (`error`/total de `frigus_graph_runs_total`); falta validar contra scrape real |
| SRE: custo/ROI | ⚠️ | `evals/sre_report.py` calcula; `VALOR_POR_RESOLUCAO_USD` é placeholder até ter dado de negócio real |
| SRE: custo por resolução | ⚠️ | `evals/sre_report.py`: resolução = `frigus_graph_runs_total{outcome="success"}`, custo pela tabela `PRECOS_POR_1M_TOKENS` |
| Desenho de arquitetura | ✅ | README — Mermaid + `assets/diagrama-agentes.png` |
| Extra: Redis fila/ranking | ✅ | `infra/redis/ranking.py` — ranking de produtos mais desperdiçados (`ZINCRBY`/`ZREVRANGE`) |
| Extra: Neo4j | ⚠️ | `neomodel` no `pyproject.toml`, conexão lazy, models (`User`/`Ingredient`/`Recipe`), tools de preferências e traversal (`sugerir_receitas_compativeis`) já expostas ao LLM. Falta sync automático Postgres→Neo4j (produtos/receitas) e mapear `fatos`→relações do grafo |
| Avaliação da disciplina | ⚠️ | Métricas de runtime movidas pra `observability/`; `evals/` agora só avaliação offline (`sre_report.py` + `scenarios.py`/`run_scenarios.py`). Harness nunca rodou de ponta a ponta (sem Docker no ar) |

## P0 — o que mais pesa na nota

1. ~~**Relatórios de SRE**~~ — feito em `evals/sre_report.py`: script que lê os contadores
   Prometheus (`frigus_llm_tokens_total`, `frigus_graph_runs_total`, `frigus_rate_limit_rejections_total`)
   via HTTP API e calcula custo total, índice de erros, custo por resolução, ROI e a projeção
   para 100/1000 usuários/semana. Definições assumidas documentadas no docstring do módulo:
   resolução = `outcome="success"` no grafo; preços por modelo em `PRECOS_POR_1M_TOKENS` (lista
   pública, conferir antes de usar em relatório oficial); volume/usuário e valor por resolução
   são placeholders (`MENSAGENS_POR_USUARIO_SEMANA`, `VALOR_POR_RESOLUCAO_USD`) até existir dado
   real — trocar essas constantes quando houver. Falta rodar contra o Prometheus real (scrape
   acumulado, não só métricas de um processo local) pra virar o relatório final da disciplina.

2. ~~**Escolher UMA superfície A2A.**~~ — feito: `a2a.py` (SDK) removido, só resta
   `api/routes/a2a.py` (manual). Decisão registrada no AGENTS.md ("Estrutura").

3. ~~**Redis com fila ou ranking.**~~ — feito: `infra/redis/ranking.py` (`ZINCRBY`/`ZREVRANGE`),
   alimentado por `estoque_repository.descartar` → `graph/tools/estoque/repo.py:discard_product`
   (falha no Redis não derruba o descarte, que já commitou no Postgres) e exposto como tool
   `ranking_desperdicio` no domínio financeiro. Testado em `tests/infra/redis/test_ranking.py`,
   `tests/tools/estoque/test_repo.py` e `tests/tools/financeiro/test_repo.py`.

## P1

1. ~~**`GET /chats` sem schema**~~ — feito: `ChatSummaryResponse` (chat_id, resume, created_at,
   updated_at), sem vazar `messages`/`user_id` crus do Mongo. ~~**Ownership no `DELETE /chats/{id}`**~~
   — feito: chama `validar_ownership` antes de agendar `encerrar_sessao`, 403 pra não-dono
   (testado em `test_chats.py`).
2. ~~**Migrar `compras`**~~ — feito: `repositories/compras_repository.py` (SQLAlchemy +
   `@transacional`), `graph/tools/compras/repo.py` chama o repository em vez de SQL cru.
   O pool `psycopg2` (`infra/postgres/connection.py`) e `next_id` cursor-based
   (`infra/postgres/helpers.py`) foram removidos — nada mais usa SQL cru no projeto.
   `health.py` (`/health/ready`) trocado pra usar a session SQLAlchemy. Testado só com mock
   do repository (`tests/tools/compras/test_repo.py`), igual todo o resto do projeto — sem
   Docker no ar não deu pra validar contra Postgres real; considerar isso antes de fechar
   o requisito como 100%.
3. **MCP ponta a ponta** com cliente externo.
4. **Rodar `evals/run_scenarios.py` de ponta a ponta** contra infra viva (Docker + API keys) e
   guardar o relatório — hoje só o `--demo` (lógica pura de match/agregação) foi validado.

## P2 — extras

1. ~~**Neo4j: tool de traversal.**~~ — feito: `sugerir_receitas_compativeis` exposta dentro de
   `RECEITAS_TOOLS`. Falta real: sync automático Postgres→Neo4j (nunca existiu, só seed manual
   em `cql/`) e mapear `fatos` (`user_fatos`) pras relações `ALLERGIC_TO`/`PREFERS`/`DISLIKES` —
   ver `.agents/notes/pending/neo4j/arquivos.md`.
2. ~~**Perfil estruturado (Mongo + Qdrant).**~~ — decisão revisada: em vez de mesclar o perfil
   texto-livre com Mongo+Qdrant, o perfil foi **removido** (nunca era lido pelo grafo) e a
   memória ficou só em `fatos` (`user_fatos`), já estruturado. `restricoes` normalizado pra
   vocabulário canônico (`schemas/models.py:RESTRICOES_CANONICAS`). Falta real: injetar `fatos`
   de volta no prompt do chat (candidato: Orquestrador) e, só depois, avaliar Qdrant/embedding
   pra busca semântica — ver `.agents/notes/pending/memoria-fatos/arquivos.md`.
3. **IDs seguros contra concorrência.** Domínios Postgres ainda resolvem próximo ID por
   `MAX(id) + 1` em vez de sequence/identity ou outro mecanismo transacional seguro — race
   condition sob concorrência real (dois inserts simultâneos podem calcular o mesmo próximo ID).
   Não bloqueia a nota, mas é debt técnico real; considerar antes de declarar "IDs seguros" em
   qualquer relatório.

## Dívida registrada: `evals/` mente o nome

~~Resolvida~~ — `metrics.py`/`metrics_callback.py` movidos pra `src/frigus_ai/observability/`
(13 imports de runtime atualizados, `git mv` preservando histórico). `evals/` agora só tem
avaliação offline: `sre_report.py` (custo/erro/ROI, já existia) e o harness novo
(`scenarios.py` + `run_scenarios.py`, 7 cenários cobrindo os 5 domínios + guardrail). Decisão
registrada no AGENTS.md ("Estrutura").

O harness em si ainda não rodou de ponta a ponta — precisa de infra viva (Postgres/Mongo/Redis/
Qdrant + API keys), que não estava disponível na sessão em que foi escrito. Só o `--demo`
(lógica de match de palavra-chave e agregação, sem tocar em infra) foi validado.

## Critério de evidência

Para cada requisito, manter em `evals/` pelo menos um cenário ou relatório que permita demonstrar
o comportamento sem depender de chamada manual não reproduzível. Não commitar prompts, respostas
com PII, credenciais ou chaves de API.
