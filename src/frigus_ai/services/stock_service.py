"""Casos de uso das rotas de estoque. Persistência crua fica em `repositories/estoque_repository.py`."""

import asyncio

from frigus_ai.graph.tools.estoque.helpers import compute_product_status
from frigus_ai.infra.logging import Logging
from frigus_ai.infra.redis import ranking
from frigus_ai.repositories import estoque_repository
from frigus_ai.repositories.estoque_repository import FiltrosEstoque, ProdutoNovo
from frigus_ai.schemas.stock import (
    StockItemCreate,
    StockItemCreateResponse,
    StockItemDiscardResponse,
    StockItemQuantityResponse,
    StockItemResponse,
    StockItemUpdate,
)

logger = Logging.get_logger(__name__)


class StockService:
    async def listar(self, stock_id: int, filtros: FiltrosEstoque) -> list[StockItemResponse]:
        itens = await asyncio.to_thread(estoque_repository.consultar_estoque, stock_id, filtros)

        return [StockItemResponse(**item) for item in itens]

    async def criar(self, stock_id: int, payload: StockItemCreate) -> StockItemCreateResponse:
        # A tool do LLM calcula o status no meio do caminho; a rota HTTP não passa por ela.
        status_calculado = compute_product_status(payload.expire_date)
        dados = ProdutoNovo(
            product_name=payload.product_name,
            category=payload.category,
            storage_place=payload.storage_place,
            quantity=payload.quantity,
            minimal_quantity=payload.minimal_quantity,
            expire_date=payload.expire_date,
            product_status=status_calculado,
            unit_price=payload.unit_price,
        )
        item_id, quantidade = await asyncio.to_thread(estoque_repository.adicionar_produto, stock_id, dados)

        return StockItemCreateResponse(
            stock_product_id=item_id, quantity=quantidade, product_status=status_calculado
        )

    async def atualizar_quantidade(
        self, stock_id: int, user_id: str, item_id: int, payload: StockItemUpdate
    ) -> StockItemQuantityResponse:
        novo_id, quantidade = await asyncio.to_thread(
            estoque_repository.atualizar_quantidade,
            stock_id, user_id, item_id, None, payload.delta, payload.novo_valor,
        )

        return StockItemQuantityResponse(stock_product_id=novo_id, quantity=quantidade)

    async def descartar(
        self, stock_id: int, user_id: str, item_id: int, reason: str
    ) -> StockItemDiscardResponse:
        descarte = await asyncio.to_thread(
            estoque_repository.descartar, stock_id, user_id, item_id, None, reason
        )

        # Estatística do ranking, não a fonte de verdade do desperdício (essa é o Postgres
        # acima, já commitado) — falha no Redis não pode derrubar uma remoção que já deu certo.
        try:
            if descarte["quantidade_perdida"] > 0:
                ranking.registrar_descarte(stock_id, descarte["product_name"], descarte["quantidade_perdida"])
        except Exception as e:
            logger.warning("RANKING ERRO | stock_product_id=%s | %s", descarte["stock_product_id"], e)

        return StockItemDiscardResponse(stock_product_id=descarte["stock_product_id"], reason=reason)


stock_service = StockService()
