"""
Tradução dos erros de domínio (`exceptions.py`) para HTTP.

Fica registrado na app, e não em `try/except` por rota, porque as regras são as mesmas em todas
elas — e porque o handler genérico de `Exception` no fim é a rede que garante que nenhuma rota
devolva stack trace pro cliente, incluindo as que ninguém lembrou de proteger.
"""

from collections.abc import Awaitable, Callable
from typing import NamedTuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from frigus_ai.exceptions import (
    ChatDeOutroUsuario,
    ChatError,
    ChatNaoEncontrado,
    EstoqueAtualNaoDefinido,
    FalhaNoAgente,
    FrigusError,
    ItemDeCompraNaoEncontrado,
    ItemDeEstoqueNaoEncontrado,
    LimiteDeMensagensExcedido,
    ProdutoNaoCadastrado,
    QuantidadeNegativa,
)
from frigus_ai.infra.redis.keys import CHAT_TTL_TIME
from frigus_ai.logging import Logging
from frigus_ai.schemas.errors import ErrorCode, ErrorResponse

logger = Logging.get_logger(__name__)

class MapaExcecao(NamedTuple):
    excecao: type[FrigusError]
    status_code: int
    code: ErrorCode


_MAPA: list[MapaExcecao] = [
    MapaExcecao(ChatNaoEncontrado,          status.HTTP_404_NOT_FOUND,            ErrorCode.CHAT_NAO_ENCONTRADO),
    MapaExcecao(ChatDeOutroUsuario,         status.HTTP_403_FORBIDDEN,            ErrorCode.CHAT_DE_OUTRO_USUARIO),
    MapaExcecao(FalhaNoAgente,              status.HTTP_502_BAD_GATEWAY,          ErrorCode.FALHA_NO_AGENTE),
    MapaExcecao(ItemDeEstoqueNaoEncontrado, status.HTTP_404_NOT_FOUND,            ErrorCode.ESTOQUE_ITEM_NAO_ENCONTRADO),
    MapaExcecao(QuantidadeNegativa,         status.HTTP_422_UNPROCESSABLE_ENTITY, ErrorCode.QUANTIDADE_NEGATIVA),
    MapaExcecao(ItemDeCompraNaoEncontrado,  status.HTTP_404_NOT_FOUND,            ErrorCode.COMPRA_ITEM_NAO_ENCONTRADO),
    MapaExcecao(ProdutoNaoCadastrado,       status.HTTP_422_UNPROCESSABLE_ENTITY, ErrorCode.PRODUTO_NAO_CADASTRADO),
    MapaExcecao(EstoqueAtualNaoDefinido,    status.HTTP_409_CONFLICT,             ErrorCode.ESTOQUE_NAO_DEFINIDO),
]


def _resposta(status_code: int, detail: str, code: ErrorCode, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=detail, code=code).model_dump(),
        headers=headers,
    )


def _handler(status_code: int, code: ErrorCode) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return _resposta(status_code, str(exc), code)

    return handle


async def _handle_limite(request: Request, exc: Exception) -> JSONResponse:
    return _resposta(
        status.HTTP_429_TOO_MANY_REQUESTS,
        str(exc),
        ErrorCode.LIMITE_DE_MENSAGENS,
        headers={"Retry-After": str(CHAT_TTL_TIME)},
    )


async def _handle_inesperado(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Erro não tratado em {request.method} {request.url.path}")

    return _resposta(status.HTTP_500_INTERNAL_SERVER_ERROR, "Erro interno inesperado.", ErrorCode.ERRO_INTERNO)


def register_exception_handlers(app: FastAPI) -> None:
    for excecao, status_code, code in _MAPA:
        app.add_exception_handler(excecao, _handler(status_code, code))

    app.add_exception_handler(LimiteDeMensagensExcedido, _handle_limite)

    # ChatError cobre subclasse nova que ninguém mapeou ainda; Exception, o resto do mundo.
    app.add_exception_handler(ChatError, _handler(status.HTTP_502_BAD_GATEWAY, ErrorCode.ERRO_NO_CHAT))
    app.add_exception_handler(Exception, _handle_inesperado)


__all__ = ["register_exception_handlers"]
