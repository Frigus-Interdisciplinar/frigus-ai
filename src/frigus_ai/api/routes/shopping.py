"""Rotas diretas da lista de compras — mesma camada de repository que a tool do LLM
(`graph/tools/compras/repo.py`) usa."""

import asyncio

from fastapi import APIRouter, status

from frigus_ai.api.auth import CurrentUserDep
from frigus_ai.api.middleware import guard
from frigus_ai.exceptions import EstoqueAtualNaoDefinido
from frigus_ai.repositories import compras_repository
from frigus_ai.schemas.shopping import (
    ShoppingItemBoughtResponse,
    ShoppingItemCreate,
    ShoppingItemCreateResponse,
    ShoppingItemResponse,
)
from frigus_ai.services.user_service import user_service

router = APIRouter(prefix="/shopping-list", tags=["shopping-list"])


async def _resolver_stock_id(user_id: str) -> int:
    stock_id = await user_service.resolver_stock_id(user_id)
    if stock_id is None:
        raise EstoqueAtualNaoDefinido
    return stock_id


@router.get("/items")
async def list_items(
    user_id: CurrentUserDep, status_filtro: str | None = None
) -> list[ShoppingItemResponse]:
    stock_id = await _resolver_stock_id(user_id)
    itens = await asyncio.to_thread(compras_repository.consultar_lista, stock_id, status_filtro)

    return [ShoppingItemResponse(**item) for item in itens]


@router.post("/items", status_code=status.HTTP_201_CREATED)
@guard.rate_limit(requests=10, window=60)
async def create_item(payload: ShoppingItemCreate, user_id: CurrentUserDep) -> ShoppingItemCreateResponse:
    stock_id = await _resolver_stock_id(user_id)
    item_id, quantidade = await asyncio.to_thread(
        compras_repository.adicionar_item,
        stock_id, payload.product_name, payload.category, payload.storage_place, payload.quantity,
    )

    return ShoppingItemCreateResponse(shopping_list_product_id=item_id, quantity=quantidade)


@router.put("/items/{item_id}/bought")
@guard.rate_limit(requests=30, window=60)
async def mark_bought(item_id: int, user_id: CurrentUserDep) -> ShoppingItemBoughtResponse:
    stock_id = await _resolver_stock_id(user_id)
    target_id = await asyncio.to_thread(
        compras_repository.marcar_status, stock_id, item_id, None, "Comprado"
    )

    return ShoppingItemBoughtResponse(shopping_list_product_id=target_id, status="Comprado")


__all__ = ["router"]
