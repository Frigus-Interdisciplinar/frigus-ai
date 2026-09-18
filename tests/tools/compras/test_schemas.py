"""
Guardas dos args que o LLM preenche: a validação virou responsabilidade do
Pydantic (antes só o prompt e o corpo da função sabiam dessas regras).
"""

import pytest
from pydantic import ValidationError

from frigus_ai.graph.tools.compras.schemas import MarkPurchasedArgs


def test_mark_purchased_nao_aceita_pendente():
    assert MarkPurchasedArgs(shopping_list_product_id=1).status == "Comprado"
    assert MarkPurchasedArgs(shopping_list_product_id=1, status="Removido")

    with pytest.raises(ValidationError):
        MarkPurchasedArgs(shopping_list_product_id=1, status="Pendente")
