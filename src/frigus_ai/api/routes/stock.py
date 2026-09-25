"""
Rotas diretas de estoque (CRUD) — reservadas pra operação atômica ("adiciona 2L de
leite"). Raciocínio ("o que faço pro jantar?") continua no chat.

Chamam a MESMA camada de repository que `graph/tools/estoque/repo.py` (a tool do LLM)
usa, sem reimplementar a lógica — só a normalização que a tool fazia no meio do
caminho (`compute_product_status`) precisa ser repetida aqui, já que a rota HTTP não
passa por ela.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Query, UploadFile, status

from frigus_ai.api.auth import CurrentUserDep
from frigus_ai.api.middleware import guard
from frigus_ai.exceptions import EstoqueAtualNaoDefinido
from frigus_ai.graph.tools.estoque.helpers import compute_product_status
from frigus_ai.infra.redis import ranking
from frigus_ai.logging import Logging
from frigus_ai.repositories import estoque_repository
from frigus_ai.repositories.estoque_repository import FiltrosEstoque, ProdutoNovo
from frigus_ai.schemas.stock import (
    FotoAnaliseResponse,
    StockItemCreate,
    StockItemCreateResponse,
    StockItemDiscardResponse,
    StockItemQuantityResponse,
    StockItemResponse,
    StockItemUpdate,
)
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service

logger = Logging.get_logger(__name__)

router = APIRouter(prefix="/stock", tags=["stock"])

_MAX_FOTO_BYTES = 8 * 1024 * 1024


async def _resolver_stock_id(user_id: str) -> int:
    stock_id = await user_service.resolver_stock_id(user_id)
    if stock_id is None:
        raise EstoqueAtualNaoDefinido
    return stock_id


@router.get("/items")
async def list_items(
    user_id: CurrentUserDep,
    storage_place: str | None = None,
    category: str | None = None,
    product_status: str | None = None,
    product_name: str | None = None,
) -> list[StockItemResponse]:
    stock_id = await _resolver_stock_id(user_id)
    filtros = FiltrosEstoque(
        storage_place=storage_place,
        category=category,
        product_status=product_status,
        product_name=product_name,
    )
    itens = await asyncio.to_thread(estoque_repository.consultar_estoque, stock_id, filtros)

    return [StockItemResponse(**item) for item in itens]


@router.post("/items", status_code=status.HTTP_201_CREATED)
@guard.rate_limit(requests=10, window=60)
async def create_item(payload: StockItemCreate, user_id: CurrentUserDep) -> StockItemCreateResponse:
    stock_id = await _resolver_stock_id(user_id)
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


@router.put("/items/{item_id}")
@guard.rate_limit(requests=30, window=60)
async def update_item(
    item_id: int, payload: StockItemUpdate, user_id: CurrentUserDep
) -> StockItemQuantityResponse:
    stock_id = await _resolver_stock_id(user_id)
    novo_id, quantidade = await asyncio.to_thread(
        estoque_repository.atualizar_quantidade,
        stock_id, user_id, item_id, None, payload.delta, payload.novo_valor,
    )

    return StockItemQuantityResponse(stock_product_id=novo_id, quantity=quantidade)


@router.delete("/items/{item_id}")
@guard.rate_limit(requests=10, window=60)
async def delete_item(
    item_id: int, user_id: CurrentUserDep, reason: str = Query(default="Removido")
) -> StockItemDiscardResponse:
    stock_id = await _resolver_stock_id(user_id)
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


@router.post("/foto")
@guard.rate_limit(requests=5, window=60)
async def analisar_foto(foto: UploadFile, user_id: CurrentUserDep) -> FotoAnaliseResponse:
    """
    Só descreve o que reconheceu na foto — não escreve no estoque. Adicionar direto o
    que um modelo de visão "acha" que viu sujaria o estoque; quem decide vira item de
    verdade é o usuário, confirmando via `POST /stock/items`.
    """

    conteudo = await foto.read()
    if len(conteudo) > _MAX_FOTO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Foto maior que 8MB.")

    stock_id = await _resolver_stock_id(user_id)
    resposta = await chat_service.analisar_foto(user_id, stock_id, conteudo)

    return FotoAnaliseResponse(resposta=resposta)


__all__ = ["router"]
