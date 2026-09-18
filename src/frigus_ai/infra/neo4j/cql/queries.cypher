// Ordem de execução: 1. nodes.cypher  2. edges.cypher  3. queries.cypher
// Atenção: como está tudo com CREATE, executar nodes.cypher ou edges.cypher
// novamente vai criar duplicados.

MATCH (n)
RETURN n;

MATCH (a)-[r]->(b)
RETURN a, r, b;

MATCH (u:User)
RETURN u;

MATCH (i:Ingredient)
RETURN i;

MATCH (r:Recipe)
RETURN r;

MATCH (r:Recipe {id: 'recipe-1'})-[rel:REQUIRES]->(i:Ingredient)
RETURN r.name, rel, i.name;

MATCH (r:Recipe)-[:REQUIRES]->(i:Ingredient)
WHERE i.name = 'Frango'
RETURN r;

MATCH (u:User {id: 'user-1'})-[rel]->(i:Ingredient)
RETURN u, rel, i;

MATCH (u:User {id: 'user-1'})-[:PREFERS]->(i:Ingredient)
RETURN u, i;

MATCH (u:User {id: 'user-1'})-[:DISLIKES]->(i:Ingredient)
RETURN u, i;

MATCH (u:User {id: 'user-1'})-[:ALLERGIC_TO]->(i:Ingredient)
RETURN u, i;

MATCH (r1:Recipe)-[:SIMILAR_TO]->(r2:Recipe)
RETURN r1, r2;

MATCH (r:Recipe)
WHERE NOT EXISTS {
  MATCH (r)-[:REQUIRES]->(i:Ingredient)
  MATCH (:User {id: 'user-1'})-[:DISLIKES|ALLERGIC_TO]->(i)
}
RETURN r;
