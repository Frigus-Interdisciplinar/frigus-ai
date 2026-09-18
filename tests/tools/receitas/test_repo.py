"""
Camada tool de receitas: sucesso vira Response.ok, exceção vira Response.error, receita
não encontrada vira Response.error — sem bater no Postgres de verdade (o repository,
que fala com o banco, é mockado; a query em si é responsabilidade de
repositories/receitas_repository.py).
"""

from frigus_ai.graph.tools.receitas.repo import ReceitasRepo
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.repositories import receitas_repository


def test_match_recipes_to_stock_usa_o_stock_id_do_contexto(monkeypatch):
    chamado_com = {}

    def _match(stock_id, limit):
        chamado_com["args"] = (stock_id, limit)
        return [{
            "recipe_id": 1,
            "name": "Omelete",
            "matched_ingredients": 2,
            "missing_ingredients": 0,
            "nearest_expire_date": None,
            "score": 1.0,
        }]

    monkeypatch.setattr(receitas_repository, "match_recipes_to_stock", _match)

    with session_context(user_id=7, stock_id=42):
        resultado = ReceitasRepo().match_recipes_to_stock(limit=3)

    assert chamado_com["args"] == (42, 3)
    assert resultado["status"] == "ok"
    assert resultado["total_records"] == 1
    assert resultado["sugestoes"][0]["name"] == "Omelete"


def test_match_recipes_to_stock_erro_vira_response_error(monkeypatch):
    def _falha(stock_id, limit):
        raise RuntimeError("conexão caiu")

    monkeypatch.setattr(receitas_repository, "match_recipes_to_stock", _falha)

    with session_context(user_id=7, stock_id=42):
        resultado = ReceitasRepo().match_recipes_to_stock()

    assert resultado["status"] == "error"
    assert "conexão caiu" in resultado["message"]


def test_get_recipe_details_ok(monkeypatch):
    monkeypatch.setattr(
        receitas_repository,
        "get_recipe_details",
        lambda recipe_id: {
            "recipe_id": recipe_id,
            "name": "Omelete",
            "description": None,
            "instructions": "Bata os ovos.",
            "ingredientes": [],
        },
    )

    resultado = ReceitasRepo().get_recipe_details(recipe_id=1)

    assert resultado["status"] == "ok"
    assert resultado["name"] == "Omelete"


def test_get_recipe_details_nao_encontrada_vira_response_error(monkeypatch):
    monkeypatch.setattr(receitas_repository, "get_recipe_details", lambda recipe_id: None)

    resultado = ReceitasRepo().get_recipe_details(recipe_id=999)

    assert resultado["status"] == "error"
    assert "999" in resultado["message"]


def test_get_recipe_details_erro_vira_response_error(monkeypatch):
    def _falha(recipe_id):
        raise RuntimeError("timeout")

    monkeypatch.setattr(receitas_repository, "get_recipe_details", _falha)

    resultado = ReceitasRepo().get_recipe_details(recipe_id=1)

    assert resultado["status"] == "error"
