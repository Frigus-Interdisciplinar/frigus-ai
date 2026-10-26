# Visão computacional (Fase 4 do PENDENCIAS.md)

## Feito

- `POST /stock/foto` (`api/routes/stock.py`) recebe `multipart/form-data`
  (`UploadFile`, não base64 em JSON — mais simples e mais barato em payload), limite
  de 8MB (`_MAX_FOTO_BYTES`), rate limit `@guard.rate_limit(requests=5, window=60)`
  (fotos são mais caras que texto).
- Node `visao_node` (`graph/nodes/visao.py`): `with_structured_output` na Luna (antes Gemini Flash)
  (`temperature=0.1`, é tarefa factual). `category`/`storage_place` do item
  identificado reaproveitam os `Literal` de `graph/tools/estoque/schemas.py` — os
  MESMOS valores que `POST /stock/items` aceita, e como viram function-calling/schema
  pro provider, o modelo é IMPEDIDO de emitir um valor fora da lista (não é validação
  depois, é restrição na própria geração). `ItemIdentificado`/`InventarioGeladeira`
  moraram em `graph/state.py` (não em `visao.py`) e `llm_visao` em `graph/llm.py`,
  junto dos outros `llm_*` — centralização feita depois, direto no editor.
- Bypass do roteador: `decidir_apos_guardrail_entrada` (`graph/builder.py`) desvia
  pra `VISAO` quando `estado["imagem_b64"]` existe, sem passar pelo LLM de roteamento
  (ele só decide por texto). Fluxo: guardrail_entrada → visão → orquestrador → juiz →
  guardrail_saida, igual Estoque/Compras/Financeiro.
- `ChatService.analisar_foto`: `thread_id` único por chamada (`visao-{user_id}-{uuid}`,
  nunca reaproveitado) — reaproveitar o mesmo thread faria o PRÓXIMO turno de texto
  nessa thread ainda carregar a imagem antiga e cair de novo na Visão. Não salva no
  histórico de chat (`agent_chats`) nem conta rate limit de mensagens — foto não é
  conversa.
- Resposta é **texto em linguagem natural** (`{"resposta": "..."}`), não JSON
  estruturado — o Orquestrador já reescreve o `InventarioGeladeira` bruto, igual faz
  com Estoque/Compras. Só descreve o que viu; não escreve no estoque (decisão do
  plano original, pra não sujar o estoque com "achismo" de visão) — usuário confirma
  via `POST /stock/items` numa mensagem/chamada separada.
- Retry do Juiz: `no_visao` devolve `rota=visao` (`VisaoUpdate`), o `path_map` do Juiz
  tem `Route.VISAO`, e o feedback do Juiz entra no prompt da segunda chamada. `visao`
  não é rota do roteador (`RotaRoteador`): turno com foto não passa por ele.
- Thread da foto apagada no fim (`runner.descartar_thread`, chamado no `finally` de
  `analisar_foto`): o MongoDBSaver grava um checkpoint por passo, cada um com o base64
  inteiro — limpar `imagem_b64` no estado final não tiraria dos anteriores.

## Falta fazer

- `llm_visao` em `graph/llm.py` é só a Luna desde 2026-10-23. Confirmado contra o gateway real que o chat
  dela aceita `image_url` (imagem sintética de 96x96, respondeu a cor em 2,9s); ainda falta testar com fotos
  reais de geladeira.
- Verificação por item (`_itens_incertos` em `visao.py`): pergunta ao JeV/Luna, com a foto, se cada
  item aparece nela; os abaixo de `confianca_minima_item_visao` (0,7, chute) vão em `esclarecer`.
  Calibrar o limiar com fotos reais e comparar as listas do Gemini e da Luna.

## Arquivos

`src/frigus_ai/graph/nodes/visao.py`, `src/frigus_ai/graph/prompts/visao.md`,
`src/frigus_ai/graph/builder.py`, `src/frigus_ai/graph/state.py`,
`src/frigus_ai/graph/names.py`, `src/frigus_ai/services/runner.py`,
`src/frigus_ai/services/chat_service.py`, `src/frigus_ai/api/routes/stock.py`,
`src/frigus_ai/schemas/stock.py`.
