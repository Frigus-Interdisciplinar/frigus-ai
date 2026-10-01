"""Rotas finas + `Depends`: o service é trocado por `dependency_overrides`, sem monkeypatch."""

import pytest
from fastapi.testclient import TestClient

from frigus_ai.api.app import app
from frigus_ai.api.auth import get_current_user
from frigus_ai.api.deps import exigir_stock_id, get_recipe_service


class _FakeRecipeService:
    async def sugerir(self, stock_id, limit):
        assert (stock_id, limit) == (7, 3)
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
