# Visão computacional (Fase 4 do PENDENCIAS.md)

## Feito

- `POST /stock/foto` (`api/routes/stock.py`) recebe `multipart/form-data`
  (`UploadFile`, não base64 em JSON — mais simples e mais barato em payload), limite
  de 8MB (`_MAX_FOTO_BYTES`), rate limit `@guard.rate_limit(requests=5, window=60)`
  (fotos são mais caras que texto).
- Node `visao_node` (`graph/nodes/visao.py`): `with_structured_output` no Gemini Flash
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

## Falta fazer

- **`imagem_b64` não é limpo do estado**: como cada foto usa uma thread nova e
  descartável, o checkpoint do MongoDBSaver dessa thread guarda o base64 da imagem
  (alguns MB) PRA SEMPRE — a thread nunca é revisitada, então nada limpa esse
  documento. Em volume, isso acumula lixo no Mongo sem controle. Corrigir exigiria ou
  (a) `no_visao` devolver `imagem_b64=None` no update (funciona só se o campo não for
  `Annotated` com reducer que ignora `None`) ou (b) um TTL/job de limpeza pra threads
  `visao-*` — nenhum dos dois foi feito.
- Sem loop de retentativa do Juiz pra Visão: `decidir_apos_juiz` (`graph/builder.py`)
  usa `estado.get("rota", GUARDRAIL_SAIDA)` pra decidir aonde voltar se reprovado, mas
  turno de Visão nunca passa pelo roteador, então `rota` nunca é setado — na prática,
  se o Juiz reprovar uma resposta de Visão, ela vai direto pro guardrail de saída sem
  segunda tentativa (não trava nem quebra, só não re-roda a visão). Aceitável por
  enquanto; corrigir exigiria setar `rota=VISAO` em algum lugar e adicionar `VISAO` no
  `path_map` do Juiz.
- Só Gemini Flash — sem fallback pra Claude (que também tem visão) se o Gemini cair ou
  não tiver `GEMINI_API_KEY` configurada (hoje: levanta `FalhaNoAgente`, vira 502).

## Arquivos

`src/frigus_ai/graph/nodes/visao.py`, `src/frigus_ai/graph/prompts/visao.md`,
`src/frigus_ai/graph/builder.py`, `src/frigus_ai/graph/state.py`,
`src/frigus_ai/graph/names.py`, `src/frigus_ai/services/runner.py`,
`src/frigus_ai/services/chat_service.py`, `src/frigus_ai/api/routes/stock.py`,
`src/frigus_ai/schemas/stock.py`.
