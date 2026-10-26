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

## Sync Postgres → Neo4j e sugestão por estoque (feito; sync e consulta validados num Neo4j real do docker-compose)

- `repositories/grafo_receitas_repository.py`: `sincronizar` (constraints `recipe_key`/`ingredient_key`, `MERGE` por
  chave estável `local:<id>` / `product:<id>`, remove relação obsoleta, `ingredients_complete` só com ingrediente
  cadastrado, receita que saiu do catálogo fica incompleta) e `sugerir` (Cypher por estoque + vencimento).
- `RecipeService.sincronizar_grafo` roda em segundo plano no `lifespan`; `RecipeService.sugerir` usa o grafo e cai
  no cruzamento SQL se o Neo4j falhar. `GET /v1/recipes/suggestions` devolve ingredientes encontrados/faltantes,
  `reason` (priorização por vencimento) e `unverified_restrictions`.
- Identidade do ingrediente = `product_id` do Postgres, então só receitas **locais** entram. Receitas da Spoonacular
  (nomes em inglês) precisam de uma tabela de mapeamento antes de entrar no grafo.
- A escrita usa os models do neomodel (`bulk_create_or_update` por `key`, `disconnect_all` + `connect` numa transação); só `sugerir` é Cypher cru (`none()`/`any()`/list comprehension não existem no query builder).
- Pendente: `restricoes_atendidas` por receita (hoje nenhuma é
  verificada), `preferir_rapidas` (receita local não tem tempo de preparo) e rodar o cenário de demonstração.
