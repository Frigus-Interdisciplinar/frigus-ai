# Neo4j (Fase 3 do PENDENCIAS.md)

## Feito

- **Grafo só de receitas** (`Recipe -[:REQUIRES]-> Ingredient`, `Recipe -[:SIMILAR_TO]-> Recipe`).
  Preferência de usuário no grafo (`User -[:PREFERS|DISLIKES|ALLERGIC_TO]->`) foi **removida**:
  duplicava `user_fatos` (Mongo), que é preenchido automaticamente pelo chat e pelo
  `PUT /profile` e já vai pro prompt — o grafo só era preenchido se o LLM chamasse
  `definir_preferencia`, então ficava vazio e a traversal nunca era usada.
- `sugerir_receitas_compativeis` (tool, dentro de `RECEITAS_TOOLS`) lê as alergias do perfil
  via `user_service.buscar_fatos`, remove anotação ("Amendoim (filho)" → "Amendoim"), soma o
  `evitar` do LLM (o que ele não gosta) e chama `preferencias_repository.receitas_sem_ingredientes`.
  Comparação no Cypher é `toLower(i.name) CONTAINS e` — falso positivo é melhor que falso
  negativo pra alergia.
- `receitas.md` manda chamar essa tool quando houver alergia/"não gosto", além do
  `match_recipes_to_stock` (Postgres, cruza com estoque).
- Async nativo (`AsyncStructuredNode`/`adb`), sem `asyncio.to_thread`.

## Falta fazer

- **Sync automático Postgres → Neo4j nunca existiu** — o seed manual `cql/*.cypher` (2
  receitas que não batiam com o catálogo) foi removido, então o grafo começa vazio. Sem isso a
  tool sugere receitas que podem não existir no app.

## Arquivos

`src/frigus_ai/repositories/preferencias_repository.py`,
`src/frigus_ai/graph/tools/preferencias/`, `src/frigus_ai/graph/tools/__init__.py`,
`src/frigus_ai/graph/prompts/receitas.md`, `src/frigus_ai/infra/neo4j/`.
