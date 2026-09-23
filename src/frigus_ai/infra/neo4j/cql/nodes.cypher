// Nodes:
// - User
// - Ingredient
// - Recipe

CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (u:User)
REQUIRE u.id IS UNIQUE;

CREATE CONSTRAINT ingredient_id_unique IF NOT EXISTS
FOR (i:Ingredient)
REQUIRE i.id IS UNIQUE;

CREATE CONSTRAINT recipe_id_unique IF NOT EXISTS
FOR (r:Recipe)
REQUIRE r.id IS UNIQUE;

MERGE (u:User {id: 'user-1'})
  ON CREATE SET u.name = 'Davi';

MERGE (i:Ingredient {id: 'ingredient-1'})
  ON CREATE SET i.name = 'Frango', i.category = 'proteina';

MERGE (i:Ingredient {id: 'ingredient-2'})
  ON CREATE SET i.name = 'Tomate', i.category = 'vegetal';

MERGE (i:Ingredient {id: 'ingredient-3'})
  ON CREATE SET i.name = 'Arroz', i.category = 'grao';

MERGE (i:Ingredient {id: 'ingredient-4'})
  ON CREATE SET i.name = 'Coentro', i.category = 'tempero';

MERGE (r:Recipe {id: 'recipe-1'})
  ON CREATE SET r.name = 'Frango com tomate', r.preparation_time_minutes = 30, r.difficulty = 'facil';

MERGE (r:Recipe {id: 'recipe-2'})
  ON CREATE SET r.name = 'Arroz com frango', r.preparation_time_minutes = 25, r.difficulty = 'facil';
