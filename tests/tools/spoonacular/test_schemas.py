from frigus_ai.graph.tools.spoonacular.schemas import (
    ReceitaDetalhada,
    ReceitaPorIngrediente,
)


def test_detalhe_preserva_imagem_preparo_fonte_e_nutricao():
    receita = ReceitaDetalhada.model_validate(
        {
            "id": 1,
            "title": "Frango",
            "image": "https://img/1.jpg",
            "sourceName": "Fonte",
            "sourceUrl": "https://fonte/1",
            "creditsText": "Créditos",
            "analyzedInstructions": [{"name": "", "steps": [{"number": 1, "step": "Tempere."}]}],
            "nutrition": {"nutrients": [{"name": "Calories", "amount": 250.0, "unit": "kcal"}]},
        }
    )

    assert receita.image_url == "https://img/1.jpg"
    assert receita.preparo[0].steps[0].step == "Tempere."
    assert receita.source_name == "Fonte"
    assert receita.nutrition.nutrients[0].unit == "kcal"


def test_busca_por_ingrediente_preserva_imagem():
    receita = ReceitaPorIngrediente.model_validate(
        {"id": 1, "title": "x", "image": "https://img/1.jpg", "usedIngredientCount": 1, "missedIngredientCount": 0}
    )

    assert receita.image_url == "https://img/1.jpg"
