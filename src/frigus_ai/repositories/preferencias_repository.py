"""
Traversal do grafo de receitas no Neo4j (Recipe -[:REQUIRES]-> Ingredient), sem
tradução pra `Response` — isso fica em `graph/tools/preferencias/repo.py` (a tool
que o LLM chama).

O grafo não guarda preferência de usuário: alergias e gostos moram só no Mongo
(`user_fatos`), e quem chama passa a lista de ingredientes a evitar.

Async nativo (`adb`), não `asyncio.to_thread`: o driver do Neo4j já é async, ao
contrário de Postgres/Mongo (`psycopg2`/`pymongo`).
"""

from typing import TypedDict

from frigus_ai.infra.neo4j.connection import neo4j


class ReceitaCompativel(TypedDict):
    recipe_id: str
    name: str
    preparation_time_minutes: int
    difficulty: str


async def receitas_sem_ingredientes(evitar: list[str], limit: int = 10) -> list[ReceitaCompativel]:
    """
    Receitas que não usam nenhum ingrediente de `evitar`. Comparação por substring sem
    caixa ("camarão" barra "Camarão cinza") — pra alergia, falso positivo é melhor que
    falso negativo. Cypher cru: `WHERE NOT EXISTS { ... }` não tem equivalente no query
    builder do neomodel.
    """

    query = """
        MATCH (r:Recipe)
        WHERE NOT EXISTS {
            MATCH (r)-[:REQUIRES]->(i:Ingredient)
            WHERE any(e IN $evitar WHERE toLower(i.name) CONTAINS e)
        }
        RETURN r.id AS recipe_id, r.name AS name,
               r.preparation_time_minutes AS preparation_time_minutes,
               r.difficulty AS difficulty
        LIMIT $limit
    """
    params = {"evitar": [e.strip().lower() for e in evitar if e.strip()], "limit": limit}
    resultados, _ = await neo4j.client.cypher_query(query, params)

    return [
        {
            "recipe_id": recipe_id,
            "name": name,
            "preparation_time_minutes": tempo,
            "difficulty": dificuldade,
        }
        for recipe_id, name, tempo, dificuldade in resultados
    ]


__all__ = ["ReceitaCompativel", "receitas_sem_ingredientes"]
