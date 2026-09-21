from langchain_core.tools import StructuredTool

from .compras import compras_repo
from .estoque import estoque_repo
from .estoque.schemas import QueryStockArgs
from .faq import faq_repo
from .financeiro import financeiro_repo
from .receitas import receitas_repo
from .spoonacular import spoonacular_repo

ESTOQUE_TOOLS = estoque_repo.as_tools()
COMPRAS_TOOLS = compras_repo.as_tools()
RECEITAS_TOOLS = [
    *receitas_repo.as_tools(),
    StructuredTool.from_function(
        estoque_repo.query_stock, name="query_stock", args_schema=QueryStockArgs
    ),
    *spoonacular_repo.as_tools(),
]
FAQ_TOOLS = faq_repo.as_tools()
FINANCEIRO_TOOLS = financeiro_repo.as_tools()

__all__ = [
    "COMPRAS_TOOLS",
    "ESTOQUE_TOOLS",
    "FAQ_TOOLS",
    "FINANCEIRO_TOOLS",
    "RECEITAS_TOOLS",
]
