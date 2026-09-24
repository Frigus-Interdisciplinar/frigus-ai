# Plano de correção do refactor

> **Nota obsoleta — arquivada em 2026-09-23.** Escrita quando a branch `refactor/structure`
> tinha 134 testes e o contrato A2A via `a2a-sdk` ainda disputava com o manual. Hoje: 232
> testes, SDK removido (decisão em `AGENTS.md`), MCP consolidado, `/health/ready` por
> dependência, `compras` migrado, ranking Redis e Neo4j conectados, avaliações offline em
> `evals/` existindo. A lista de P0/P1/P2 abaixo não reflete mais o estado real — fonte atual
> de verdade é `pending/requisitos-disciplina/arquivos.md`. Dos itens abaixo, os que ainda são
> reais (Docker/infra viva não validada, `MAX(id)+1` sob concorrência) já estão re-registrados
> lá. Mantido só como histórico.

Atualizado após a revisão completa da branch `refactor/structure`.

## P0 — execução e contratos

- [x] Consolidar o MCP em `src/frigus_ai/mcp.py`.
- [x] Fazer `/health/ready` testar cada dependência independentemente.
- [x] Fazer `pytest` e `ruff` passarem na branch atual.
- [ ] Preencher/documentar o ambiente de execução conforme `.env.example`.
- [ ] Subir Docker Desktop e validar Postgres, Mongo, Redis, Qdrant, Prometheus e Grafana.
- [ ] Escolher um único contrato A2A (SDK ou manual) e cobri-lo com integração.

## P1 — dados, sessões e concorrência

- [ ] Substituir `MAX(id) + 1` por sequences/identity ou mecanismo transacional seguro.
- [x] Remover o mapa/lock em memória e guardar `context_id -> user_id` no Redis com `SET NX EX`.
- [ ] Vincular a sessão A2A à identidade autenticada; a integração SDK alternativa ainda usa usuário
  padrão e o histórico completo continua no Mongo/checkpointer.
- [ ] Propagar `X-API-Key` ao executor A2A SDK e remover usuário padrão do fluxo real.
- [ ] Evitar chamada duplicada de `iniciar_sessao` no executor SDK.
- [ ] Revisar índices e constraints de criação de usuário/chat sob concorrência.

## P1 — organização

- [ ] Remover fachadas `toolset.py` quando não houver imports dependentes.
- [ ] Eliminar duplicação entre funções de módulo e `ChatService`.
- [ ] Tirar bootstrap de usuário/estoque do serviço de chat.
- [ ] Consolidar `a2a.py` com `api/routes/a2a.py` após escolher o contrato.
- [ ] Corrigir `just run` para não depender de Bash nem de caminho Windows fixo.

## P2 — disciplina e observabilidade

- [ ] Criar avaliações offline para custo de 100/1000 usuários, índice de erros, ROI e custo
  por resolução.
- [ ] Definir resolução, volume de mensagens, distribuição de domínios, provider e preços.
- [ ] Validar scrape do Prometheus e dashboards Grafana com containers em execução.
- [ ] Implementar fila/ranking em Redis e o extra Neo4j com traversal demonstrável.

## Evidências

- `pytest -q`: 134 testes passando.
- `ruff check`: passou.
- `docker compose config --quiet`: passou.
- API importa com ambiente completo e registra `/metrics`.
- Docker daemon estava desligado; a execução real dos serviços ainda não foi validada.
