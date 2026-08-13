from datetime import date, timedelta

import pytest

from frigus_ai.tools.postgres.helpers import (
    CATEGORY_VALUES,
    DIAS_ATENCAO,
    STORAGE_PLACE_VALUES,
    compute_product_status,
    expiring_date_threshold,
    normalize_enum,
)

# --------------------- normalize_enum ---------------------

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("geladeira", "Geladeira"),      # case
        ("FREEZER", "Freezer"),
        ("  Despensa  ", "Despensa"),    # espaços
    ],
)
def test_normalize_enum_resolve_variacoes(entrada, esperado):
    assert normalize_enum(entrada, STORAGE_PLACE_VALUES) == esperado


def test_normalize_enum_ignora_acento():
    """O LLM escreve sem acento com frequência — 'laticinio' tem que casar com 'Laticínio'."""
    assert normalize_enum("laticinio", CATEGORY_VALUES) == "Laticínio"
    assert normalize_enum("higiene pessoal", CATEGORY_VALUES) == "Higiene Pessoal"


def test_normalize_enum_sem_correspondencia():
    assert normalize_enum("porta-malas", STORAGE_PLACE_VALUES) is None


@pytest.mark.parametrize("vazio", ["", None])
def test_normalize_enum_valor_vazio(vazio):
    assert normalize_enum(vazio, STORAGE_PLACE_VALUES) is None


# --------------------- compute_product_status ---------------------

HOJE = date(2026, 8, 13)


@pytest.mark.parametrize(
    "dias,esperado",
    [
        (-1, "Vencido"),                        # ontem
        (0, "Próximo do vencimento"),           # vence hoje, ainda não venceu
        (DIAS_ATENCAO, "Próximo do vencimento"),      # limite do amarelo
        (DIAS_ATENCAO + 1, "Fresco"),                 # primeiro dia verde
    ],
)
def test_compute_product_status(dias, esperado):
    assert compute_product_status(HOJE + timedelta(days=dias), hoje=HOJE) == esperado


def test_expiring_date_threshold():
    assert expiring_date_threshold(3) == date.today() + timedelta(days=3)
    assert expiring_date_threshold() == date.today() + timedelta(days=DIAS_ATENCAO)
