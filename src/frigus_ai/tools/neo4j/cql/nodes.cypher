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

CREATE (:User {
  id: 'user-1',
  name: 'Davi'
});

CREATE (:Ingredient {
  id: 'ingredient-1',
  name: 'Frango',
  category: 'proteina'
});

CREATE (:Ingredient {
  id: 'ingredient-2',
  name: 'Tomate',
  category: 'vegetal'
});

CREATE (:Ingredient {
  id: 'ingredient-3',
  name: 'Arroz',
  category: 'grao'
});

CREATE (:Ingredient {
  id: 'ingredient-4',
  name: 'Coentro',
  category: 'tempero'
});

CREATE (:Recipe {
  id: 'recipe-1',
  name: 'Frango com tomate',
  preparation_time_minutes: 30,
  difficulty: 'facil'
});

CREATE (:Recipe {
  id: 'recipe-2',
  name: 'Arroz com frango',
  preparation_time_minutes: 25,
  difficulty: 'facil'
});
