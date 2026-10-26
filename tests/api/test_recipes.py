"""Rotas finas + `Depends`: o service é trocado por `dependency_overrides`, sem monkeypatch."""

import pytest
from fastapi.testclient import TestClient

from frigus_ai.api.app import app
from frigus_ai.api.auth import get_current_user
from frigus_ai.api.deps import exigir_stock_id, get_recipe_service
from frigus_ai.schemas.recipes import RecipeDetailResponse


class _FakeRecipeService:
    async def sugerir(self, user_id, stock_id, limit):
        assert (user_id, stock_id, limit) == ("user-1", 7, 3)
        return []


@pytest.fixture
def cliente():
    app.dependency_overrides[get_current_user] = lambda: "user-1"
    app.dependency_overrides[exigir_stock_id] = lambda: 7
    app.dependency_overrides[get_recipe_service] = lambda: _FakeRecipeService()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_sugestoes_usam_stock_id_da_dependencia(cliente):
    r = cliente.get("/v1/recipes/suggestions?limit=3")

    assert r.status_code == 200
    assert r.json() == []


def test_detalhe_repassa_source_e_nutricao(cliente):
    class _Service:
        async def detalhar(self, user_id, source, recipe_id, include_nutrition):
            assert (source, recipe_id, include_nutrition) == ("spoonacular", 5, True)
            return RecipeDetailResponse(recipe_id=5, source=source, name="Sopa", steps=["Ferva."])

    app.dependency_overrides[get_recipe_service] = lambda: _Service()

    r = cliente.get("/v1/recipes/spoonacular/5?include_nutrition=true")

    assert r.status_code == 200
    assert r.json()["steps"] == ["Ferva."]


def test_source_invalido_vira_422(cliente):
    assert cliente.get("/v1/recipes/outra/5").status_code == 422


def test_favoritar_e_desfavoritar_respondem_204(cliente):
    chamadas = []

    class _Service:
        async def favoritar(self, user_id, source, recipe_id):
            chamadas.append(("put", user_id, source, recipe_id))

        async def desfavoritar(self, user_id, source, recipe_id):
            chamadas.append(("del", user_id, source, recipe_id))

        async def favoritas(self, user_id, limit):
            return []

    app.dependency_overrides[get_recipe_service] = lambda: _Service()

    assert cliente.put("/v1/recipes/local/3/favorite").status_code == 204
    assert cliente.delete("/v1/recipes/spoonacular/9/favorite").status_code == 204
    assert cliente.get("/v1/recipes/favorites").json() == []
    assert chamadas == [("put", "user-1", "local", 3), ("del", "user-1", "spoonacular", 9)]


def test_listagem_repassa_query(cliente):
    class _Service:
        async def listar(self, user_id, limit, query):
            assert (user_id, limit, query) == ("user-1", 50, "frango")
            return []

    app.dependency_overrides[get_recipe_service] = lambda: _Service()

    assert cliente.get("/v1/recipes?query=frango").status_code == 200
