# A2A Frigus → Assessor (plano de economia com alimentação)

## Decisão de escopo

O Frigus **não** age como proxy da conta do usuário no Assessor (saldo, registrar gasto): a
`ASSESSOR_API_KEY` é uma só, e no Assessor cada key pertence a um usuário (`/v1/keys`,
`/v1/users`) — todo usuário do Frigus veria/gravaria na mesma conta. Resolver isso exigiria
vincular contas (cada usuário colar a key dele, guardada criptografada por usuário).

Em vez disso, o Frigus manda os dados que só ele tem (gasto com comida no mês e no anterior,
valor descartado, itens mais desperdiçados) junto com a pergunta, e pede ao Assessor a análise
(orçamento de mercado, plano de economia). A key vira conta de serviço. Saldo/conta/registrar
gasto: o roteador responde `fim` dizendo que isso é no app do Assessor.

## Feito

- Nó `a2a_assessor_node` (`A2A_ASSESSOR`, rota `assessor`, `AssessorUpdate`) em
  `graph/nodes/assessor.py`: monta o contexto com `financeiro_repository` + ranking do Redis
  (via `to_thread`, leva o `session_context`), manda pergunta + dados, devolve o texto. Sem
  dado (sem estoque, Postgres/Redis fora) pergunta sem contexto em vez de falhar.
- Cliente em `infra/assessor/client.py`: A2A **1.0** conferido no OpenAPI do deploy
  (`assessor-ai.fastapicloud.dev/openapi.json`) — `SendMessage`, header `A2A-Version: 1.0`,
  `ROLE_USER`, parts `{"text"}`, resposta `{"message"}`/`{"task"}`, auth `X-API-Key`. Toda
  falha vira `AssessorIndisponivel`.
- `context_id` = `uuid5` do `session_id`: mesmo chat, mesma sessão no Assessor, sem guardar
  mapeamento (Redis não é necessário — é determinístico).
- Grafo: roteador → assessor → juiz → saída (texto pronto, sem orquestrador). Indisponível →
  `dados_especialista` vazio → `decidir_apos_assessor` pula o Juiz. O Juiz recebe os números
  enviados em `dados_especialista` pra conferir a resposta.
- Roteador: `financeiro` = consultar número; `assessor` = conselho/plano; conta/saldo = `fim`.
- Skill `planejamento_alimentar_a2a` no Agent Card do Frigus.
- Frontend: `a2a_assessor_node` em tipos, lista de nós, layout, arestas e ícone.

## Falta fazer

- **Testar contra o Assessor rodando.** Só exercitado contra `MockTransport`. O Agent Card do
  deploy não foi lido (o WAF bloqueou o `curl`). Se o Assessor local for 0.3 (`message/send`),
  não conversa com este cliente.
- **Conta de serviço vazia no Assessor.** Se o grafo de lá sempre puxar perfil/transações do
  dono da key, pode misturar na resposta — a mensagem pede pra não usar, mas o garantido é a
  conta não ter nada.
- **Sugestão pro repo do Assessor (fora daqui):** a skill `moneysaving` do card dele dizer que
  aceita dados de gasto enviados por quem chama. Não é obrigatório — skill é descoberta, o
  servidor não recusa mensagem por ela.
- `pergunta_original` chega anonimizada (tokens `[PII_...]`) — irrelevante pro escopo atual.

## Arquivos

`src/frigus_ai/graph/nodes/assessor.py`, `src/frigus_ai/infra/assessor/client.py`,
`src/frigus_ai/graph/{builder,names,state}.py`, `src/frigus_ai/graph/prompts/router.md`,
`src/frigus_ai/api/routes/a2a.py`, `src/frigus_ai/settings.py`, `.env.example`,
`web/src/{types.ts,lib/*.ts,components/chat/node-icon.tsx}`,
`tests/infra/assessor/test_client.py`, `tests/graph/nodes/test_assessor.py`, `tests/graph/test_builder.py`.
