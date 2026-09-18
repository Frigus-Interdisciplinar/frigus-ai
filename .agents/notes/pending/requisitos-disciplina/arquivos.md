# Requisitos da disciplina — o que falta

Conferido contra o código em `refactor/structure` (suíte: 177 passed).
Antes de reportar item como pendente, confira o código: este checklist envelhece.

## Placar

| Requisito | Status | Onde / o que falta |
| --- | --- | --- |
| API FastAPI/Flask | ⚠️ | `api/` com health, chats, keys, MCP e A2A. Falta: schema de resposta em `GET /chats` (hoje `list[dict]`), versionamento e ownership no `DELETE /chats/{id}` |
| Multiagente (mín. 5 agentes) | ✅ | 10 nós (`graph/names.py`) |
| LangChain pra criar agentes | ✅ | `graph/agents.py` |
| LangGraph pra orquestrar | ✅ | `graph/builder.py`, com `input_schema`/`output_schema` e contrato `AsyncNode[R]` |
| Sessões por usuário | ⚠️ | `thread_id=session_id` no `MongoDBSaver` + histórico no Mongo. Ownership fechado em `send_message`, `get_messages` e `/stream`; falta no `DELETE` |
| Memória de longo prazo | ✅ | Perfil no Mongo (`user_profiles`), regenerado do resumo no `encerrar_sessao` |
| MCP | ⚠️ | `mcp.py` expõe as tools com `X-API-Key`. Falta validação externa ponta a ponta |
| A2A | ⚠️ | **Duas superfícies vivas**: `a2a.py` (SDK) e `api/routes/a2a.py` (manual). Escolher uma |
| RAG com fonte externa | ✅ | `graph/tools/faq/` — Qdrant sobre `data/pdf/Frigus-Documentacao.pdf` |
| Agente juiz | ✅ | `graph/nodes/juiz.py` — grounding/relevância, até 2 retentativas |
| Guardrail | ✅ | `graph/guardrail/` — entrada (PII + ataque + classificador com cache) e saída |
| SRE: latência interagentes | ✅ | Prometheus mede HTTP, grafo, node, tool e LLM; dashboard Grafana com 8 painéis |
| SRE: custo 100 e 1000 usuários/semana | ❌ | Tokens são coletados; falta virar estimativa documentada |
| SRE: índice de erros | ⚠️ | Contadores existem; falta fórmula, janela e relatório |
| SRE: custo/ROI | ❌ | Falta valor de resolução, premissas e cálculo reproduzível |
| SRE: custo por resolução | ❌ | Depende de definir "resolução" |
| Desenho de arquitetura | ✅ | README — Mermaid + `assets/diagrama-agentes.png` |
| Extra: Redis fila/ranking | ❌ | Redis só faz cache (perfil, guardrail), rate limit, sessão A2A e api-key. **Cache não conta** pro requisito |
| Extra: Neo4j | ❌ | Só `.cypher` em `infra/neo4j/cql/`. Sem driver no `pyproject.toml`, sem conexão, sem traversal |

## P0 — o que mais pesa na nota

1. **Relatórios de SRE** (4 itens ❌/⚠️ num bloco só). Nada disso precisa de código novo de
   produção: é script em `evals/` lendo os contadores que já existem. Definir antes:
   - o que conta como "resolução" (turno que terminou sem bloqueio do guardrail? Juiz aprovado?);
   - preço por 1k tokens do provider em uso, por modelo (`llm_rapido` vs `llm_especialista`);
   - volume e distribuição de domínios dos dois cenários (100 e 1000 usuários/semana).

2. **Escolher UMA superfície A2A.** `a2a.py` (SDK) e `api/routes/a2a.py` (manual) coexistem
   e podem divergir. Enquanto as duas existirem, nenhum teste prova o contrato real.

3. **Redis com fila ou ranking.** O enunciado pede um dos dois; cache e rate limit não contam.
   Ideia que cabe no domínio sem inventar dado: ranking de itens mais desperdiçados por estoque
   (`ZINCRBY` no `discard`), que já tem fonte de dado real em `stock_movements`/`discard`.

## P1

1. **`GET /chats` sem schema** (`list[dict]`) e ownership no `DELETE /chats/{id}` (hoje devolve
   202 pra não-dono; não vaza dado porque `encerrar_sessao` é escopado, mas o status mente).
2. **Migrar `compras`** — último domínio em SQL cru (5 `get_conn`).
3. **MCP ponta a ponta** com cliente externo.

## P2 — extras

1. **Neo4j.** Sem driver ainda. Recomendação: driver oficial + Cypher num `Neo4jRepo` espelhando
   o `PostgresRepo` — **não** usar OGM (neomodel). O requisito é "pergunta de negócio respondida
   por traversal", e um OGM esconde exatamente o traversal que está sendo avaliado.
   Atenção à regra do AGENTS.md: o traversal tem que rodar sobre dado que o sistema coleta
   (produtos/receitas/ingredientes), **não** sobre preferências — o perfil no Mongo é texto livre.
2. **Perfil estruturado (Mongo + Qdrant).** Discussão da sessão: dá pra mesclar — Mongo como
   fonte da verdade com chaves obrigatórias, Qdrant pra busca semântica sobre as notas livres.
   Bloqueio: `prompts/perfil.md` manda o LLM gerar **texto livre de até 6 linhas**; sem mudar o
   prompt pra emitir estrutura, não há chave nenhuma pra gravar. Ordem: prompt → Mongo com
   schema → Qdrant só se a busca semântica provar ganho.

## Dívida registrada: `evals/` mente o nome

A nota anterior decidiu que métricas de runtime **não** deveriam morar em `evals/`.
Hoje moram: `evals/metrics.py` e `evals/metrics_callback.py` são importados por **13 módulos de
runtime**, incluindo todos os nós do grafo. E o harness de avaliação offline não existe.
Ou move pra `observability/` e deixa `evals/` pra avaliação, ou reescreve a decisão. Enquanto
não resolver, o item "Avaliação da disciplina" não pode ser marcado como feito.

## Critério de evidência

Para cada requisito, manter em `evals/` pelo menos um cenário ou relatório que permita demonstrar
o comportamento sem depender de chamada manual não reproduzível. Não commitar prompts, respostas
com PII, credenciais ou chaves de API.
