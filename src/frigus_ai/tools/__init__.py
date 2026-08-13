from .postgres.estoque.core import (
    add_stock_product,
    query_stock,
    update_stock_quantity,
    discard_product,
)
from .postgres.compras.core import (
    create_shopping_list,
    add_shopping_list_product,
    query_shopping_list,
    mark_purchased,
    generate_shopping_list_from_low_stock,
    register_purchase_from_nfe,
)
from .postgres.receitas.core import (
    match_recipes_to_stock,
    get_recipe_details,
)
from .postgres.financeiro.core import (
    gastos_mensais,
    comparacao_mensal,
    valor_descartado,
    evolucao_desperdicio,
)

from .faq_tools import faq_retriever

ESTOQUE_TOOLS = [add_stock_product, query_stock, update_stock_quantity, discard_product]
COMPRAS_TOOLS = [
    create_shopping_list,
    add_shopping_list_product,
    query_shopping_list,
    mark_purchased,
    generate_shopping_list_from_low_stock,
    register_purchase_from_nfe,
]
RECEITAS_TOOLS = [match_recipes_to_stock, get_recipe_details]
FAQ_TOOLS = [faq_retriever]
FINANCEIRO_TOOLS = [gastos_mensais, comparacao_mensal, valor_descartado, evolucao_desperdicio]

__all__ = [
    "ESTOQUE_TOOLS",
    "COMPRAS_TOOLS",
    "RECEITAS_TOOLS",
    "FAQ_TOOLS",
    "FINANCEIRO_TOOLS",
]
