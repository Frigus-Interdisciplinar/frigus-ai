"""
Dependências compartilhadas das rotas: usuário, estoque e services. Rota só recebe HTTP e delega;
nos testes, `app.dependency_overrides` troca qualquer um destes.
"""

from typing import Annotated

from fastapi import Depends

from frigus_ai.api.auth import CurrentUserDep
from frigus_ai.services.auth_service import AuthService, auth_service
from frigus_ai.services.chat_service import ChatService
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.recipe_service import RecipeService, recipe_service
from frigus_ai.services.shopping_service import ShoppingService, shopping_service
from frigus_ai.services.stock_service import StockService, stock_service
from frigus_ai.services.user_service import UserService, user_service


def get_chat_service() -> ChatService:
    return chat_service


def get_user_service() -> UserService:
    return user_service


def get_auth_service() -> AuthService:
    return auth_service


def get_stock_service() -> StockService:
    return stock_service


def get_shopping_service() -> ShoppingService:
    return shopping_service


def get_recipe_service() -> RecipeService:
    return recipe_service


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
StockServiceDep = Annotated[StockService, Depends(get_stock_service)]
ShoppingServiceDep = Annotated[ShoppingService, Depends(get_shopping_service)]
RecipeServiceDep = Annotated[RecipeService, Depends(get_recipe_service)]


async def exigir_stock_id(user_id: CurrentUserDep, users: UserServiceDep) -> int:
    """Rotas de estoque/compras/receitas não têm o que fazer sem estoque — vira 409."""

    return await users.exigir_stock_id(user_id)


async def stock_id_opcional(user_id: CurrentUserDep, users: UserServiceDep) -> int | None:
    """Chat funciona sem estoque associado; só o domínio de estoque exige."""

    return await users.resolver_stock_id(user_id)


StockIdDep = Annotated[int, Depends(exigir_stock_id)]
OptionalStockIdDep = Annotated[int | None, Depends(stock_id_opcional)]

__all__ = [
    "AuthServiceDep",
    "ChatServiceDep",
    "CurrentUserDep",
    "OptionalStockIdDep",
    "RecipeServiceDep",
    "ShoppingServiceDep",
    "StockIdDep",
    "StockServiceDep",
    "UserServiceDep",
]
