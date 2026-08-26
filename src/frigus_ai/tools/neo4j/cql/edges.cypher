// Edges:
// - User -[:PREFERS]-> Ingredient
// - User -[:DISLIKES]-> Ingredient
// - User -[:ALLERGIC_TO]-> Ingredient
// - Recipe -[:REQUIRES]-> Ingredient
// - Recipe -[:SIMILAR_TO]-> Recipe

MATCH (u:User {id: 'user-1'})
MATCH (i:Ingredient {id: 'ingredient-1'})
CREATE (u)-[:PREFERS]->(i);

MATCH (u:User {id: 'user-1'})
MATCH (i:Ingredient {id: 'ingredient-4'})
CREATE (u)-[:DISLIKES]->(i);

MATCH (u:User {id: 'user-1'})
MATCH (i:Ingredient {id: 'ingredient-4'})
CREATE (u)-[:ALLERGIC_TO]->(i);

MATCH (r:Recipe {id: 'recipe-1'})
MATCH (i:Ingredient {id: 'ingredient-1'})
CREATE (r)-[:REQUIRES {
  quantity: 300,
  unit: 'g'
}]->(i);

MATCH (r:Recipe {id: 'recipe-1'})
MATCH (i:Ingredient {id: 'ingredient-2'})
CREATE (r)-[:REQUIRES {
  quantity: 2,
  unit: 'unidade'
}]->(i);

MATCH (r:Recipe {id: 'recipe-1'})
MATCH (i:Ingredient {id: 'ingredient-3'})
CREATE (r)-[:REQUIRES {
  quantity: 1,
  unit: 'xicara'
}]->(i);

MATCH (r:Recipe {id: 'recipe-2'})
MATCH (i:Ingredient {id: 'ingredient-1'})
CREATE (r)-[:REQUIRES {
  quantity: 250,
  unit: 'g'
}]->(i);

MATCH (r:Recipe {id: 'recipe-2'})
MATCH (i:Ingredient {id: 'ingredient-3'})
CREATE (r)-[:REQUIRES {
  quantity: 2,
  unit: 'xicara'
}]->(i);

MATCH (r1:Recipe {id: 'recipe-1'})
MATCH (r2:Recipe {id: 'recipe-2'})
CREATE (r1)-[:SIMILAR_TO]->(r2);
