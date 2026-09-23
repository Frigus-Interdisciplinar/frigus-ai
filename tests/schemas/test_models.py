"""
`Fatos.restricoes` é o único campo de vocabulário fechado (`alergias`/`preferencias`/
`habitos` são livres de propósito) — o `field_validator` roda em toda construção de
`Fatos`: saída do LLM de extração, merge automático e `PUT /profile` manual.
"""

from frigus_ai.schemas.models import Fatos


def test_normaliza_grafia_diferente_pro_valor_canonico():
    assert Fatos(restricoes=["vegetariano"]).restricoes == ["Vegetariano"]
    assert Fatos(restricoes=["SEM LACTOSE"]).restricoes == ["Sem lactose"]
    assert Fatos(restricoes=["sem gluten"]).restricoes == ["Sem glúten"]  # sem acento


def test_mantem_valor_cru_quando_nao_reconhece():
    assert Fatos(restricoes=["janta cedo"]).restricoes == ["janta cedo"]


def test_dedupe_apos_normalizar():
    fatos = Fatos(restricoes=["vegetariano", "Vegetariano", "VEGETARIANO"])

    assert fatos.restricoes == ["Vegetariano"]


def test_preserva_ordem_de_chegada():
    fatos = Fatos(restricoes=["low carb", "vegano", "algo nao mapeado"])

    assert fatos.restricoes == ["Low carb", "Vegano", "algo nao mapeado"]


def test_lista_vazia_continua_vazia():
    assert Fatos().restricoes == []
