"""Casos de uso das rotas da lista de compras. Persistência crua em `repositories/compras_repository.py`."""

import asyncio

from frigus_ai.repositories import compras_repository
from frigus_ai.schemas.shopping import (
    ShoppingItemBoughtResponse,
    ShoppingItemCreate,
    ShoppingItemCreateResponse,
    ShoppingItemResponse,
)


class ShoppingService:
    async def listar(self, stock_id: int, status_filtro: str | None) -> list[ShoppingItemResponse]:
        itens = await asyncio.to_thread(compras_repository.consultar_lista, stock_id, status_filtro)

        return [ShoppingItemResponse(**item) for item in itens]

    async def adicionar(self, stock_id: int, payload: ShoppingItemCreate) -> ShoppingItemCreateResponse:
        item_id, quantidade = await asyncio.to_thread(
            compras_repository.adicionar_item,
            stock_id, payload.product_name, payload.category, payload.storage_place, payload.quantity,
        )

        return ShoppingItemCreateResponse(shopping_list_product_id=item_id, quantity=quantidade)

    async def marcar_comprado(self, stock_id: int, item_id: int) -> ShoppingItemBoughtResponse:
        target_id = await asyncio.to_thread(
            compras_repository.marcar_status, stock_id, item_id, None, "Comprado"
        )

        return ShoppingItemBoughtResponse(shopping_list_product_id=target_id, status="Comprado")


shopping_service = ShoppingService()
