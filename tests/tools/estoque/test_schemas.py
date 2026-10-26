"""
Guardas dos args que o LLM preenche: a validação virou responsabilidade do
Pydantic (antes só o prompt e o corpo da função sabiam dessas regras).
"""

import pytest
from pydantic import ValidationError

from frigus_ai.graph.tools.estoque.schemas import (
    AddStockProductArgs,
    UpdateStockQuantityArgs,
)


def test_update_stock_exige_delta_ou_novo_valor_exclusivos():
    assert UpdateStockQuantityArgs(product_name="leite", delta=-1).delta == -1
    assert UpdateStockQuantityArgs(product_name="leite", novo_valor=3).novo_valor == 3

    for kwargs in ({}, {"delta": 1, "novo_valor": 3}, {"novo_valor": -1}):
        with pytest.raises(ValidationError):
            UpdateStockQuantityArgs(product_name="leite", **kwargs)


@pytest.mark.parametrize("campo, valor", [("quantity", 0), ("quantity", -2), ("unit_price", -1), ("minimal_quantity", -1)])
def test_cadastro_por_tool_recusa_quantidade_e_preco_invalidos(campo, valor):
    base = {
        "product_name": "Leite",
        "category": "Laticínio",
        "storage_place": "Geladeira",
        "quantity": 1,
        "expire_date": "2030-01-01",
    }

    with pytest.raises(ValidationError):
        AddStockProductArgs(**{**base, campo: valor})
