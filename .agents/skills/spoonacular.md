# Spoonacular Food API

Client externo pra dados de receita/ingrediente (`tools/spoonacular/` — a criar). Base URL
`https://api.spoonacular.com`, auth por query param `apiKey` em toda chamada. Docs oficiais:
[spoonacular.com/food-api/docs](https://spoonacular.com/food-api/docs).

## Tier gratuito — por que cache é obrigatório, não otimização

**50 pontos/dia, 1 req/s, 2 requisições concorrentes.** Estourou o limite, toda chamada devolve
`402` até resetar (meia-noite UTC). A maioria dos endpoints abaixo custa mais que 1 ponto por
chamada (cresce com `number` de resultados) — na prática são **poucas dezenas de chamadas por dia**,
não por minuto. Qualquer coisa chamada em loop (ex. resolver ingrediente por ingrediente de uma
receita) estoura a cota rápido. Por isso a tabela de lookup Spoonacular↔estoque discutida no TODO
(cache em Mongo) não é luxo — sem ela, o segundo turno do dia já não tem mais cota pra chamar a API
de novo pro mesmo ingrediente.

Antes de subir `SPOONACULAR_API_KEY` real: confirmar se o tier gratuito cobre o uso do time (mesma
cautela já aplicada em Observabilidade/Infisical no TODO.md — a disciplina não paga API paga).

## Endpoints que vamos usar

### Ingredient Search

`GET /ingredients/search`

| Param | Tipo | Default | Obs |
|---|---|---|---|
| `query` | string | — | obrigatório |
| `number` | int | 10 | 1–100 |
| `intolerances` | string | — | filtro |
| `sort` / `sortDirection` | string | — / `asc` | |
| `offset` | int | 0 | |

Resposta: array de `{id, name, image, aisle, possibleUnits}`. **Custo: 1 ponto/chamada.**

### Get Ingredient Information

`GET /ingredients/{id}/information`

| Param | Tipo | Default |
|---|---|---|
| `id` (path) | int | obrigatório |
| `amount` | number | 1 |
| `unit` | string | — |

Resposta: `{id, name, image, nutrition, properties, possibleUnits}`. **Custo: 1 ponto/chamada.** `id`
é o identificador estável — é a chave que a tabela de lookup Spoonacular↔estoque usa, não o `name`.

### Search Recipes by Ingredients

`GET /recipes/findByIngredients`

| Param | Tipo | Default | Obs |
|---|---|---|---|
| `ingredients` | string | — | obrigatório, lista separada por vírgula |
| `number` | int | 10 | 1–100 |
| `ranking` | int | 1 | 1 = maximiza usados, 2 = minimiza faltando |
| `ignorePantry` | bool | false | ignora item de despensa (sal, água, etc.) |

Resposta: array com `id, title, image, usedIngredients, missedIngredients, unusedIngredients,
usedIngredientCount, missedIngredientCount`. **Custo: 1 ponto + 0.01/receita retornada.** É o
endpoint mais direto pro caso de uso "receita com o que já tem no estoque" — `ranking=2` prioriza
menos ingrediente faltando, que é o que interessa aqui.

### Search Recipes by Nutrients

`GET /recipes/findByNutrients`

Pares min/max por nutriente (`minCalories`/`maxCalories`, `minProtein`/`maxProtein`, `minFat`/
`maxFat`, `minCarbs`/`maxCarbs`, etc.), mais `offset` (default 0, 0–900), `number` (default 10,
1–100), `random` (bool, default false).

Resposta: array com `id, title, image, calories, protein, fat, carbs`. **Custo: 1 ponto +
0.01/receita retornada.**

### Get Recipe Information

`GET /recipes/{id}/information`

| Param | Tipo | Default |
|---|---|---|
| `id` (path) | int | obrigatório |
| `includeNutrition` | bool | false |
| `addWinePairing` | bool | false |
| `addTasteData` | bool | false |

Resposta: objeto completo — `id, title, image, servings, readyInMinutes, extendedIngredients`
(com quantidade/unidade por ingrediente — é daqui que vem a lista pra cruzar com o estoque),
`cuisines, diets, healthScore, summary`. **Custo: 1 ponto + 0.1 (nutrição) + 1 (harmonização de
vinho) + 0.5 (perfil de sabor)** — não ligar essas flags sem precisar, cada uma soma pontos.

### Get Similar Recipes

`GET /recipes/{id}/similar`

| Param | Tipo | Default | Obs |
|---|---|---|---|
| `id` (path) | int | obrigatório | |
| `number` | int | 10 | 1–100 |

Resposta: array com `id, title, imageType, readyInMinutes, servings, sourceUrl`. **Custo: 1 ponto +
0.01/receita retornada.**

## Client HTTP

Ainda não existe (`tools/spoonacular/` não foi criado). Usar `httpx` (ver
[other-tools.md](other-tools.md) — ainda não é dependência do projeto, adicionar com `uv add httpx`
junto da primeira tool que fizer a chamada real). Mesmo padrão de `connection.py` lazy que
`tools/mongo/` e `tools/postgres/` já seguem — client HTTP configurado uma vez, não por chamada.

---

# Pegadinhas deste repo

Ainda nenhuma — client não implementado. Adicione uma entrada quando encontrar um comportamento real
da API que não bate com a documentação acima (campo ausente, custo de ponto diferente do
documentado, rate limit mais agressivo na prática, etc.).
