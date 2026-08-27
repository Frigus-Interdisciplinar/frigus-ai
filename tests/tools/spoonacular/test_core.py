import httpx
import pytest

from frigus_ai.tools.spoonacular import core


@pytest.fixture(autouse=True)
def _isola(monkeypatch):
    monkeypatch.setattr(core.settings, "SPOONACULAR_API_KEY", "test-key")
    core._get.cache_clear()
    yield
    core._get.cache_clear()


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "erro", request=httpx.Request("GET", "http://x"), response=self
            )


class _FakeClient:
    def __init__(self, resposta):
        self._resposta = resposta
        self.chamadas = []

    def get(self, path, params=None, timeout=None):
        self.chamadas.append((path, dict(params or {})))
        return self._resposta


def _fake(monkeypatch, json_data, status_code=200):
    fake = _FakeClient(_FakeResponse(json_data, status_code))
    monkeypatch.setattr(core, "cliente", fake)
    return fake


def test_find_recipes_mapeia_resultado_e_params(monkeypatch):
    fake = _fake(monkeypatch, [
        {
            "id": 1,
            "title": "Omelete",
            "usedIngredientCount": 2,
            "missedIngredientCount": 1,
            "missedIngredients": [{"name": "queijo"}],
        }
    ])

    r = core.find_recipes_by_ingredients.invoke(
        {"ingredients": ["ovo", "cebola"], "number": 5}
    )

    assert r["status"] == "ok"
    assert r["receitas"] == [
        {"id": 1, "title": "Omelete", "used_count": 2, "missed_count": 1, "missed": ["queijo"]}
    ]

    path, params = fake.chamadas[0]
    assert path == "/recipes/findByIngredients"
    assert params["ingredients"] == "ovo,cebola"
    assert params["ignorePantry"] is True
    assert params["ranking"] == 2


def test_get_recipe_information_traduz_aliases(monkeypatch):
    _fake(monkeypatch, {
        "id": 42,
        "title": "Sopa",
        "readyInMinutes": 30,
        "servings": 4,
        "extendedIngredients": [{"name": "cebola", "amount": 1, "unit": "un"}],
        "instructions": "Ferva.",
        "healthScore": 99,  # campo extra ignorado
    })

    r = core.get_recipe_information.invoke({"recipe_id": 42})

    assert r == {
        "status": "ok",
        "id": 42,
        "title": "Sopa",
        "ready_in_minutes": 30,
        "servings": 4,
        "ingredientes": [{"nome": "cebola", "quantidade": 1.0, "unidade": "un"}],
        "instrucoes": "Ferva.",
    }


def test_payload_sem_campo_obrigatorio_vira_response_error(monkeypatch):
    _fake(monkeypatch, [{"title": "sem id"}])

    r = core.find_recipes_by_ingredients.invoke({"ingredients": ["ovo"]})

    assert r["status"] == "error"


def test_cota_esgotada_vira_response_error(monkeypatch):
    _fake(monkeypatch, {"message": "quota"}, status_code=402)

    r = core.find_recipes_by_ingredients.invoke({"ingredients": ["ovo"]})

    assert r["status"] == "error"
    assert "cota" in r["message"].lower()


def test_cache_evita_segunda_chamada(monkeypatch):
    fake = _fake(monkeypatch, [])

    core.find_recipes_by_ingredients.invoke({"ingredients": ["ovo"]})
    core.find_recipes_by_ingredients.invoke({"ingredients": ["ovo"]})

    assert len(fake.chamadas) == 1


def test_sem_api_key_nao_chama_a_api(monkeypatch):
    fake = _fake(monkeypatch, [])
    monkeypatch.setattr(core.settings, "SPOONACULAR_API_KEY", "")

    r = core.find_recipes_by_ingredients.invoke({"ingredients": ["ovo"]})

    assert r["status"] == "error"
    assert fake.chamadas == []
