from frigus_ai.graph.tools.spoonacular.schemas import ReceitaDetalhada
from frigus_ai.services import recipe_service as modulo
from frigus_ai.services.recipe_service import RecipeService, _etapas


def test_etapas_remove_html_e_quebra_por_tag():
    assert _etapas("<ol><li>Pique.</li><li>Asse.</li></ol>") == ["Pique.", "Asse."]
    assert _etapas(None) == []


async def test_detalhe_spoonacular_prefere_etapas_estruturadas(monkeypatch):
    async def fake(recipe_id, include_nutrition):
        return ReceitaDetalhada.model_validate({
            "id": recipe_id,
            "title": "Frango",
            "instructions": "<p>texto solto</p>",
            "analyzedInstructions": [{"steps": [{"number": 1, "step": "Tempere."}]}],
            "nutrition": {"nutrients": [{"name": "Calories", "amount": 250, "unit": "kcal"}]},
        })

    monkeypatch.setattr(modulo, "detalhar_receita", fake)

    r = await RecipeService()._detalhe("spoonacular", 1, True)

    assert r.steps == ["Tempere."]
    assert r.nutrients[0].unit == "kcal"


async def test_favoritar_guarda_retrato_do_card_e_marca_is_favorite(monkeypatch):
    salvos = []
    monkeypatch.setattr(modulo.favoritos_repository, "favoritar", lambda u, f: salvos.append((u, f)))
    monkeypatch.setattr(
        modulo.favoritos_repository,
        "listar_favoritos",
        lambda u, limit: [{"source": "spoonacular", "recipe_id": 1, "name": "Frango", "image_url": "i"}],
    )

    async def fake(recipe_id, include_nutrition):
        return ReceitaDetalhada.model_validate({"id": recipe_id, "title": "Frango", "image": "i"})

    monkeypatch.setattr(modulo, "detalhar_receita", fake)

    service = RecipeService()
    await service.favoritar("u1", "spoonacular", 1)
    detalhe = await service.detalhar("u1", "spoonacular", 1, False)

    assert salvos == [("u1", {"source": "spoonacular", "recipe_id": 1, "name": "Frango", "image_url": "i"})]
    assert detalhe.is_favorite is True


async def test_sugerir_monta_parametros_do_grafo_e_explica_a_prioridade(monkeypatch):
    from datetime import date, timedelta

    from frigus_ai.domain.models import Fatos, RecipePreferences
    from frigus_ai.repositories import grafo_receitas_repository
    from frigus_ai.services.user_service import user_service

    amanha = date.today() + timedelta(days=1)
    recebidos = {}

    async def _fatos(user_id):
        return Fatos(alergias=["Amendoim (filho)"])

    async def _prefs(user_id):
        return RecipePreferences(restricoes=["Vegano"], preferir_economicas=True)

    async def _sugerir(**kwargs):
        recebidos.update(kwargs)
        return [{
            "recipe_id": 4, "name": "Omelete", "score": 0.5,
            "encontrados": [{"key": "product:9", "name": "Ovo"}],
            "prioritarios": ["Ovo"], "faltantes": ["Sal"],
        }]

    monkeypatch.setattr(user_service, "buscar_fatos", _fatos)
    monkeypatch.setattr(user_service, "buscar_preferencias_receitas", _prefs)
    monkeypatch.setattr(
        modulo.receitas_repository, "estoque_utilizavel",
        lambda stock_id, dias: [
            {"key": "product:9", "name": "Ovo", "expire_date": amanha, "prioritario": True},
            {"key": "product:3", "name": "Leite", "expire_date": amanha + timedelta(days=30), "prioritario": False},
        ],
    )
    monkeypatch.setattr(grafo_receitas_repository, "sugerir", _sugerir)

    (sugestao,) = await RecipeService().sugerir("u1", 7, 5)

    assert recebidos["evitar"] == ["Amendoim"]
    assert recebidos["disponiveis"] == ["product:9", "product:3"]
    assert recebidos["prioritarios"] == ["product:9"]
    assert recebidos["preferir_economicas"] is True
    assert sugestao.nearest_expire_date == str(amanha)
    assert "vence em até" in sugestao.reason
    assert sugestao.unverified_restrictions == ["Vegano"]


async def test_sugerir_cai_pro_sql_quando_o_neo4j_falha(monkeypatch):
    async def _quebra(*_):
        raise ConnectionError("neo4j fora")

    monkeypatch.setattr(RecipeService, "_sugerir_pelo_grafo", _quebra)
    monkeypatch.setattr(
        modulo.receitas_repository, "match_recipes_to_stock",
        lambda stock_id, limit: [{
            "recipe_id": 1, "name": "x", "matched_ingredients": 1, "missing_ingredients": 0,
            "nearest_expire_date": None, "score": 1.0,
        }],
    )

    sugestoes = await RecipeService().sugerir("u1", 7, 5)

    assert [s.recipe_id for s in sugestoes] == [1]
