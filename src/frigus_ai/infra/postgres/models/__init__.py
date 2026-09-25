"""
Models SQLAlchemy das tabelas do Supabase (schema `public`) — só os domínios que o app
usa hoje (estoque, compras, receitas; financeiro reaproveita as tabelas de estoque).
O schema tem outras tabelas (accounts, conversations, messages, requests,
compartilhadas com outras apps do grupo) que não estão mapeadas aqui de propósito —
`alembic/env.py:include_object` ignora tabelas refletidas sem contraparte no metadata,
então elas não aparecem como DROP num futuro `alembic revision --autogenerate`.
"""

from .base import Base
from .compras import ShoppingList, ShoppingListProduct
from .estoque import (
    AJUSTE,
    ENTRADA,
    SAIDA,
    VENCIDO,
    Discard,
    Product,
    StockMovement,
    StockProduct,
)
from .identity import Group, Stock, User, UserGroup
from .receitas import Recipe, RecipeIngredient, RecipeSuggestion

__all__ = [
    "AJUSTE",
    "ENTRADA",
    "SAIDA",
    "VENCIDO",
    "Base",
    "Discard",
    "Group",
    "Product",
    "Recipe",
    "RecipeIngredient",
    "RecipeSuggestion",
    "ShoppingList",
    "ShoppingListProduct",
    "Stock",
    "StockMovement",
    "StockProduct",
    "User",
    "UserGroup",
]
