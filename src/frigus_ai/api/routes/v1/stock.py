"""
Rotas diretas de estoque (CRUD) — reservadas pra operação atômica ("adiciona 2L de
leite"). Raciocínio ("o que faço pro jantar?") continua no chat. Regras em
`services/stock_service.py`, que chama a MESMA camada de repository que a tool do LLM
(`graph/tools/estoque/repo.py`) usa.
"""

from fastapi import APIRouter, HTTPException, Query, UploadFile, status

from frigus_ai.api.deps import (
    ChatServiceDep,
    CurrentUserDep,
    StockIdDep,
    StockServiceDep,
)
from frigus_ai.api.middleware import guard
from frigus_ai.repositories.estoque_repository import FiltrosEstoque
from frigus_ai.schemas.stock import (
    FotoAnaliseResponse,
    StockItemCreate,
    StockItemCreateResponse,
    StockItemDiscardResponse,
    StockItemQuantityResponse,
    StockItemResponse,
    StockItemUpdate,
)

router = APIRouter(prefix="/stock", tags=["stock"])

_MAX_FOTO_BYTES = 8 * 1024 * 1024


@router.get(
    "/items",
    summary="Listar itens do estoque",
)
async def list_items(
    stock_id: StockIdDep,
    service: StockServiceDep,
    storage_place: str | None = None,
    category: str | None = None,
    product_status: str | None = None,
    product_name: str | None = None,
) -> list[StockItemResponse]:
    """Filtros opcionais por local, categoria, status e nome."""

    filtros = FiltrosEstoque(
        storage_place=storage_place,
        category=category,
        product_status=product_status,
        product_name=product_name,
    )

    return await service.listar(stock_id, filtros)


@router.post(
    "/items",
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar item ao estoque",
    responses={
        429: {"description": "Limite de 10 por minuto."},
    },
)
@guard.rate_limit(requests=10, window=60)
async def create_item(
    payload: StockItemCreate, stock_id: StockIdDep, service: StockServiceDep
) -> StockItemCreateResponse:
    return await service.criar(stock_id, payload)


@router.put(
    "/items/{item_id}",
    summary="Atualizar quantidade do item",
    responses={
        429: {"description": "Limite de 30 por minuto."},
    },
)
@guard.rate_limit(requests=30, window=60)
async def update_item(
    item_id: int,
    payload: StockItemUpdate,
    user_id: CurrentUserDep,
    stock_id: StockIdDep,
    service: StockServiceDep,
) -> StockItemQuantityResponse:
    return await service.atualizar_quantidade(stock_id, user_id, item_id, payload)


@router.delete(
    "/items/{item_id}",
    summary="Descartar item",
    responses={
        429: {"description": "Limite de 10 por minuto."},
    },
)
@guard.rate_limit(requests=10, window=60)
async def delete_item(
    item_id: int,
    user_id: CurrentUserDep,
    stock_id: StockIdDep,
    service: StockServiceDep,
    reason: str = Query(default="Removido"),
) -> StockItemDiscardResponse:
    """Remove o item do estoque registrando o motivo (`reason`)."""

    return await service.descartar(stock_id, user_id, item_id, reason)


@router.post(
    "/foto",
    summary="Analisar foto",
    responses={
        413: {"description": "Foto maior que 8MB."},
        415: {"description": "O arquivo não é uma imagem."},
        429: {"description": "Limite de 5 por minuto."},
    },
)
@guard.rate_limit(requests=5, window=60)
async def analisar_foto(
    foto: UploadFile, user_id: CurrentUserDep, stock_id: StockIdDep, chat: ChatServiceDep
) -> FotoAnaliseResponse:
    """
    Só descreve o que reconheceu na foto — não escreve no estoque. Adicionar direto o
    que um modelo de visão "acha" que viu sujaria o estoque; quem decide vira item de
    verdade é o usuário, confirmando via `POST /stock/items`.
    """

    if not (foto.content_type or "").startswith("image/"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Envie uma imagem.")

    # Lê no máximo 1 byte além do limite: arquivo grande não entra inteiro na RAM.
    conteudo = await foto.read(_MAX_FOTO_BYTES + 1)
    if len(conteudo) > _MAX_FOTO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Foto maior que 8MB.")

    resposta = await chat.analisar_foto(user_id, stock_id, conteudo)

    return FotoAnaliseResponse(resposta=resposta)


__all__ = ["router"]
