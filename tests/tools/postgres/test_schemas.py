"""
Guardas dos args que o LLM preenche: a validação virou responsabilidade do
Pydantic (antes só o prompt e o corpo da função sabiam dessas regras).
"""

import pytest
from pydantic import ValidationError

from frigus_ai.tools.postgres.compras.schemas import MarkPurchasedArgs
from frigus_ai.tools.postgres.estoque.schemas import UpdateStockQuantityArgs
from frigus_ai.tools.postgres.financeiro.schemas import EvolucaoDesperdicioArgs, MesArgs


def test_update_stock_exige_delta_ou_novo_valor_exclusivos():
    assert UpdateStockQuantityArgs(product_name="leite", delta=-1).delta == -1
    assert UpdateStockQuantityArgs(product_name="leite", novo_valor=3).novo_valor == 3

    for kwargs in ({}, {"delta": 1, "novo_valor": 3}, {"novo_valor": -1}):
        with pytest.raises(ValidationError):
            UpdateStockQuantityArgs(product_name="leite", **kwargs)


def test_mark_purchased_nao_aceita_pendente():
    assert MarkPurchasedArgs(shopping_list_product_id=1).status == "Comprado"
    assert MarkPurchasedArgs(shopping_list_product_id=1, status="Removido")

    with pytest.raises(ValidationError):
        MarkPurchasedArgs(shopping_list_product_id=1, status="Pendente")


def test_mes_precisa_ser_yyyy_mm():
    assert MesArgs(mes="2026-08").mes == "2026-08"
    assert MesArgs().mes is None

    for invalido in ("agosto", "2026-13", "26-08", "2026-8"):
        with pytest.raises(ValidationError):
            MesArgs(mes=invalido)


def test_evolucao_desperdicio_exige_meses_positivo():
    assert EvolucaoDesperdicioArgs().meses == 6

    with pytest.raises(ValidationError):
        EvolucaoDesperdicioArgs(meses=0)
