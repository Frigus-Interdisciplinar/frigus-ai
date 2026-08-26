from .postgres.compras.core import (
    add_shopping_list_product,
    create_shopping_list,
    generate_shopping_list_from_low_stock,
    mark_purchased,
    query_shopping_list,
    register_purchase_from_nfe,
)
from .postgres.estoque.core import (
    add_stock_product,
    discard_product,
    query_stock,
    update_stock_quantity,
)
from .postgres.financeiro.core import (
    comparacao_mensal,
    evolucao_desperdicio,
    gastos_mensais,
    valor_descartado,
)
from .postgres.receitas.core import (
    get_recipe_details,
    match_recipes_to_stock,
)
from .qdrant.faq.core import faq_retriever

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
    "COMPRAS_TOOLS",
    "ESTOQUE_TOOLS",
    "FAQ_TOOLS",
    "FINANCEIRO_TOOLS",
    "RECEITAS_TOOLS",
]
