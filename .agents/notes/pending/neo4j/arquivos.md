# Neo4j / preferências (Fase 3 do PENDENCIAS.md)

## Feito

- `preferencias_repository.definir_preferencia` cria o node `User` no grafo na
  primeira preferência (`_obter_ou_criar_usuario`, `bulk_get_or_create` com
  `merge_by={"keys": ["uid"]}` — sem isso o MERGE cairia no default de
  `__required_properties__`, que pra `User` é só `name`, e colidiria usuários
  diferentes com o mesmo nome). `listar_preferencias`/`remover_preferencia` num
  usuário sem node no grafo devolvem vazio/no-op em vez de `DoesNotExist`.
- Query de recomendação (`WHERE NOT EXISTS` com dois `MATCH` aninhados — sem
  equivalente no query builder do neomodel, por isso Cypher cru via `neomodel.db`)
  exposta como `receitas_sem_restricoes` no repository e `sugerir_receitas_compativeis`
  como tool do LLM.
- `PREFERENCIAS_TOOLS` estava definido mas não conectado a nenhum node do grafo —
  dobrado dentro de `RECEITAS_TOOLS` (decisão do usuário: preferência é a mesma
  conversa de comida que receitas, não merece rota própria). `router.md` e
  `receitas.md` atualizados pra o LLM saber que pode registrar/consultar
  preferência e usar `sugerir_receitas_compativeis`.
- `cql/nodes.cypher` e `cql/edges.cypher`: `CREATE` → `MERGE`, idempotentes agora
  (eram só seed manual pra Neo4j Browser — nenhum código Python os executa).
- **Async nativo, não `asyncio.to_thread`**: `User`/`Ingredient`/`Recipe`/`Requires`
  agora são `AsyncStructuredNode`/`AsyncRelationshipTo`/`AsyncStructuredRel` (neomodel
  7 tem API async de verdade — a suposição de "neomodel é só síncrono" no plano
  original estava desatualizada). `infra/neo4j/connection.py` expõe `adb`, não `db`.
  `preferencias_repository.py` e `graph/tools/preferencias/repo.py` inteiros viraram
  `async def`/`await` — sem `to_thread` porque não há chamada bloqueante real por
  baixo (ao contrário de Postgres/Mongo, que são clients síncronos de verdade). A
  tool segue o mesmo padrão de `graph/tools/spoonacular/repo.py`:
  `StructuredTool.from_function(wrapper_sync_com_asyncio.run, coroutine=metodo_async, ...)`.

## Falta fazer

- **Sync automático Postgres → Neo4j nunca existiu** (havia um `ingest.py`
  referenciado em `__pycache__`, mas o arquivo fonte não está no repo — só o seed
  manual em `cql/`). Sem isso, `Ingredient`/`Recipe` no grafo só existem se alguém
  rodar o `.cypher` na mão; a query de recomendação não enxerga produtos/receitas
  reais do Postgres.
- Mapeamento fatos (`user_fatos`, ver `.agents/notes/pending/memoria-fatos/`) →
  relações `ALLERGIC_TO`/`PREFERS`/`DISLIKES` do grafo — hoje só existe o caminho
  manual via `definir_preferencia` (tool chamada pelo LLM durante a conversa).

## Arquivos

`src/frigus_ai/repositories/preferencias_repository.py`,
`src/frigus_ai/graph/tools/preferencias/`, `src/frigus_ai/graph/tools/__init__.py`,
`src/frigus_ai/graph/prompts/receitas.md`, `src/frigus_ai/graph/prompts/router.md`,
`src/frigus_ai/infra/neo4j/cql/`.
