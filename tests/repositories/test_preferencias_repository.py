"""
Traversal de receitas no Neo4j: o que se checa é o que o repository manda pro Cypher
e como monta o retorno — sem bater no Neo4j de verdade.
"""

from frigus_ai.repositories import preferencias_repository as repo_module


async def test_receitas_sem_ingredientes_normaliza_evitar_e_monta_dicts(monkeypatch):
    async def _cypher_query(query, params):
        assert params == {"evitar": ["camarão", "coentro"], "limit": 5}
        return [["recipe-1", "Frango com tomate", 30, "facil"]], None

    monkeypatch.setattr(repo_module.neo4j.client, "cypher_query", _cypher_query)

    resultado = await repo_module.receitas_sem_ingredientes(["Camarão", "  Coentro ", " "], 5)

    assert resultado == [{
        "recipe_id": "recipe-1",
        "name": "Frango com tomate",
        "preparation_time_minutes": 30,
        "difficulty": "facil",
    }]
