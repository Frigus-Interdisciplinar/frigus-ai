"""
Tradução dos erros de domínio (`domain/errors.py`) para HTTP.

Fica registrado na app, e não em `try/except` por rota, porque as regras são as mesmas em todas
elas — e porque o handler genérico de `Exception` no fim é a rede que garante que nenhuma rota
devolva stack trace pro cliente, incluindo as que ninguém lembrou de proteger.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from frigus_ai.api.errors.responses import ErrorResponse
from frigus_ai.domain.errors import DomainError, ErrorCode, LimiteDeMensagensExcedido
from frigus_ai.infra.logging import Logging
from frigus_ai.infra.redis.keys import CHAT_TTL_TIME

logger = Logging.get_logger(__name__)


def _resposta(
    request: Request, status_code: int, detail: str, code: ErrorCode, headers: dict[str, str] | None = None
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=detail, code=code, request_id=request_id).model_dump(),
        headers=headers,
    )


async def _handle_domain(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    logger.warning("%s em %s %s: %s", type(exc).__name__, request.method, request.url.path, exc)
    headers = {"Retry-After": str(CHAT_TTL_TIME)} if isinstance(exc, LimiteDeMensagensExcedido) else None
    return _resposta(request, exc.status_code, exc.public_message, exc.code, headers)


async def _handle_inesperado(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro não tratado em %s %s", request.method, request.url.path)

    return _resposta(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Erro interno inesperado.", ErrorCode.ERRO_INTERNO)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain)
    app.add_exception_handler(Exception, _handle_inesperado)


__all__ = ["register_exception_handlers"]
