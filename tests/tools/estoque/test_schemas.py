"""
Guardas dos args que o LLM preenche: a validação virou responsabilidade do
Pydantic (antes só o prompt e o corpo da função sabiam dessas regras).
"""

import pytest
from pydantic import ValidationError

from frigus_ai.graph.tools.estoque.schemas import UpdateStockQuantityArgs


def test_update_stock_exige_delta_ou_novo_valor_exclusivos():
    assert UpdateStockQuantityArgs(product_name="leite", delta=-1).delta == -1
    assert UpdateStockQuantityArgs(product_name="leite", novo_valor=3).novo_valor == 3

    for kwargs in ({}, {"delta": 1, "novo_valor": 3}, {"novo_valor": -1}):
        with pytest.raises(ValidationError):
            UpdateStockQuantityArgs(product_name="leite", **kwargs)
