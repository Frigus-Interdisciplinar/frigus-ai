# Memória incremental de fatos (Fase 2 do PENDENCIAS.md)

## Feito

- Coleção `user_fatos` no Mongo (`repositories/fatos_repository.py`), schema único
  `Fatos` (`schemas/models.py`, Pydantic — usado como saída do LLM via
  `with_structured_output`, formato de `/profile` e retorno do repository).
- Extração a cada 10 mensagens (`ChatService._talvez_atualizar_memoria`), disparada em
  segundo plano (`asyncio.create_task` com referência guardada em
  `_tarefas_em_segundo_plano`, não `BackgroundTasks` do FastAPI — `send_message`
  também é chamado por A2A/MCP/TUI, não só por uma rota HTTP).
- **Resumo do chat também virou periódico** (mesmo gatilho/janela de fatos, mesma
  chamada em segundo plano — `ChatService._atualizar_memoria` faz os dois numa leitura
  só do documento). Antes só rodava no `DELETE /chats/{id}` (`encerrar_sessao`), como
  "full pass" sobre a conversa inteira: sessão nunca fechada ficava com `resume`
  vazio pra sempre — mesmo bug que motivou a extração periódica de fatos, só que
  nunca corrigido pro resumo até agora. Virou incremental (resumo atual + mensagens
  novas → resumo atualizado, prompt `resumidor.md`, mesmo formato do antigo
  `perfil.md`), então além de nunca ficar vazio também não faz um "full pass" caro
  toda vez. `encerrar_sessao` agora só cobre o rabo de mensagens que ainda não bateu
  o intervalo (pula se `total % _INTERVALO_ATUALIZACAO_MEMORIA == 0` — o ciclo
  periódico já cobriu, rodar de novo repetiria a mesma chamada de LLM à toa).
- Regra de segurança: `UserService.atualizar_fatos_por_extracao` só **adiciona**
  alergia (união com o que já existia); `sobrescrever_fatos` (`PUT /profile`) é o
  único caminho que remove.
- `GET/PUT /profile` (`api/routes/profile.py`).
- **Normalização de `restricoes`**: `RESTRICOES_CANONICAS` + `_normalizar_restricao`
  (`schemas/models.py`) — vocabulário fechado (vegetariano, vegano, sem lactose, sem
  glúten, kosher, halal, low carb, sem açúcar, sem frutos do mar, sem carne vermelha).
  Roda num `field_validator` de `Fatos.restricoes`, então cobre os três construtores
  (extração do LLM, merge automático, `PUT /profile`) sem precisar chamar nada à mão.
  Sem correspondência, mantém o valor cru (nunca descarta) — mesmo espírito do
  `normalize_enum` de `graph/tools/estoque/helpers.py`, mas duplicado ali por baixo
  (função privada `_sem_acento` local) em vez de importado, pra não inverter a direção
  de dependência (`schemas/` é importado por `graph/tools/`, não o contrário).
  `prompts/fatos.md` ganhou uma dica com os termos canônicos pra aumentar a taxa de
  match já na extração. Testes em `tests/schemas/test_models.py`.

## Decisão: perfil comportamental (texto livre) removido

`perfil_usuario` (`user_profiles`, texto livre de até 6 linhas gerado por LLM a partir
do resumo da sessão) foi removido inteiro — `repositories/user_repository.py`,
`prompts/perfil.md`, o campo em `EntradaGrafo`/`Estado`, `_gerar_perfil`/
`atualizar_perfil_pelo_resumo`/cache Redis em `user_service.py`, e a passagem por
`runner.py`/`chat_service.py`. Nunca era lido por nenhum node do grafo (confirmado por
grep antes da remoção); em vez de resolver esse gap injetando texto livre no prompt,
a decisão foi manter só a memória estruturada (`fatos`/`user_fatos`) e investir em
normalizá-la — mais fácil de virar filtro/relação (Neo4j) e de embeddar de forma
consistente do que prosa gerada por LLM a cada encerramento de sessão.

## Falta fazer

- **Injeção no prompt do chat**: `fatos` também não é lido de volta pelo grafo hoje —
  só é usado na extração/merge (`chat_service._atualizar_memoria`) e exposto via
  `GET/PUT /profile`. Decidir QUAL node injeta fatos no prompt (candidato natural: o
  Orquestrador, que já monta a resposta final) é trabalho futuro, depois da
  normalização — não faz sentido embutir `restricoes` sujo no contexto do LLM.
- Mapeamento fatos → `Ingredient.id` do Neo4j pras relações
  `ALLERGIC_TO`/`PREFERS`/`DISLIKES` (depende da normalização acima e da Fase 3).
- **Qdrant/embedding** (abordagem alternativa ao pedido original da disciplina): depois
  de normalizado, `restricoes`/`preferencias` são candidatos a busca semântica; hoje
  não há nenhum embedding de `fatos`/perfil, só o FAQ (`graph/tools/faq/`) usa Qdrant.

## Arquivos

`src/frigus_ai/repositories/{fatos_repository,chat_repository}.py`,
`src/frigus_ai/services/chat_service.py`, `src/frigus_ai/services/user_service.py`,
`src/frigus_ai/schemas/models.py`, `src/frigus_ai/api/routes/profile.py`,
`src/frigus_ai/graph/prompts/{fatos,resumidor}.md`.
