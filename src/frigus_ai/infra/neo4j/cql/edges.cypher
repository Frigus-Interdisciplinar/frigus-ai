// Edges:
// - User -[:PREFERS]-> Ingredient
// - User -[:DISLIKES]-> Ingredient
// - User -[:ALLERGIC_TO]-> Ingredient
// - Recipe -[:REQUIRES]-> Ingredient
// - Recipe -[:SIMILAR_TO]-> Recipe

MATCH (u:User {id: 'user-1'})
MATCH (i:Ingredient {id: 'ingredient-1'})
MERGE (u)-[:PREFERS]->(i);

MATCH (u:User {id: 'user-1'})
MATCH (i:Ingredient {id: 'ingredient-4'})
MERGE (u)-[:DISLIKES]->(i);

MATCH (u:User {id: 'user-1'})
MATCH (i:Ingredient {id: 'ingredient-4'})
MERGE (u)-[:ALLERGIC_TO]->(i);

MATCH (r:Recipe {id: 'recipe-1'})
MATCH (i:Ingredient {id: 'ingredient-1'})
MERGE (r)-[rel:REQUIRES]->(i)
  ON CREATE SET rel.quantity = 300, rel.unit = 'g';

MATCH (r:Recipe {id: 'recipe-1'})
MATCH (i:Ingredient {id: 'ingredient-2'})
MERGE (r)-[rel:REQUIRES]->(i)
  ON CREATE SET rel.quantity = 2, rel.unit = 'unidade';

MATCH (r:Recipe {id: 'recipe-1'})
MATCH (i:Ingredient {id: 'ingredient-3'})
MERGE (r)-[rel:REQUIRES]->(i)
  ON CREATE SET rel.quantity = 1, rel.unit = 'xicara';

MATCH (r:Recipe {id: 'recipe-2'})
MATCH (i:Ingredient {id: 'ingredient-1'})
MERGE (r)-[rel:REQUIRES]->(i)
  ON CREATE SET rel.quantity = 250, rel.unit = 'g';

MATCH (r:Recipe {id: 'recipe-2'})
MATCH (i:Ingredient {id: 'ingredient-3'})
MERGE (r)-[rel:REQUIRES]->(i)
  ON CREATE SET rel.quantity = 2, rel.unit = 'xicara';

MATCH (r1:Recipe {id: 'recipe-1'})
MATCH (r2:Recipe {id: 'recipe-2'})
MERGE (r1)-[:SIMILAR_TO]->(r2);
