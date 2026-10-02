"""Rotas diretas da lista de compras — regras em `services/shopping_service.py`."""

from fastapi import APIRouter, status

from frigus_ai.api.deps import ShoppingServiceDep, StockIdDep
from frigus_ai.api.middleware import guard
from frigus_ai.schemas.shopping import (
    ShoppingItemBoughtResponse,
    ShoppingItemCreate,
    ShoppingItemCreateResponse,
    ShoppingItemResponse,
)

router = APIRouter(prefix="/shopping-list", tags=["shopping-list"])


@router.get(
    "/items",
    summary="Listar lista de compras",
)
async def list_items(
    stock_id: StockIdDep, service: ShoppingServiceDep, status_filtro: str | None = None
) -> list[ShoppingItemResponse]:
    """`status_filtro` opcional filtra pelo status do item."""

    return await service.listar(stock_id, status_filtro)


@router.post(
    "/items",
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar item à lista",
    responses={
        422: {"description": "Produto fora do catálogo sem `category` e `storage_place`."},
        429: {"description": "Limite de 10 por minuto."},
    },
)
@guard.rate_limit(requests=10, window=60)
async def create_item(
    payload: ShoppingItemCreate, stock_id: StockIdDep, service: ShoppingServiceDep
) -> ShoppingItemCreateResponse:
    """
    Produto que já está no catálogo só precisa de `product_name` e `quantity`. Produto novo exige
    também `category` e `storage_place`, que o cadastram no catálogo.
    """

    return await service.adicionar(stock_id, payload)


@router.put(
    "/items/{item_id}/bought",
    summary="Marcar item como comprado",
    responses={
        429: {"description": "Limite de 30 por minuto."},
    },
)
@guard.rate_limit(requests=30, window=60)
async def mark_bought(
    item_id: int, stock_id: StockIdDep, service: ShoppingServiceDep
) -> ShoppingItemBoughtResponse:
    return await service.marcar_comprado(stock_id, item_id)


__all__ = ["router"]
