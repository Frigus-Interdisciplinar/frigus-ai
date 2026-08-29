from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from config.logging import get_logger
from frigus_ai.chat.service import LimiteDeMensagensExcedido
from frigus_ai.tools.redis.schemas import CHAT_TTL_TIME
from frigus_ai.tools.spoonacular.connection import fechar_client
from interfaces.api.routes import (
    a2a_router,
    chats_router,
    health_router,
    keys_router,
)
from interfaces.mcp.server import lifespan_mcp
from interfaces.mcp.server import montar_app as montar_app_mcp

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_mcp():
        yield
    # httpx.Client segura o pool de conexões; sem isso o shutdown deixa socket
    # aberto (e o pytest reclama de recurso não fechado).
    fechar_client()


app = FastAPI(
    title="Frigus.AI",
    description="API do assistente conversacional do Frigus",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(LimiteDeMensagensExcedido)
async def limite_excedido(request: Request, exc: LimiteDeMensagensExcedido) -> JSONResponse:
    """
    O rate limit é regra de domínio (`chat/service.py`) e vale pra toda rota que fala
    com o grafo — traduzir pra 429 em cada uma delas era a mesma dúzia de linhas em
    `/chats/{id}/messages`, no SSE e no `/a2a`.
    """

    return JSONResponse(
        {"detail": str(exc)},
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(CHAT_TTL_TIME)},
    )


@app.exception_handler(Exception)
async def erro_interno(request: Request, exc: Exception) -> JSONResponse:
    """
    Traceback no log, texto fixo no corpo. `str(exc)` de exceção não prevista devolveria
    a mensagem crua do psycopg2/pymongo (usuário, senha, fragmento de query) pro cliente.
    """

    logger.exception("Falha não tratada | %s %s", request.method, request.url.path)

    return JSONResponse(
        {"detail": "Erro interno ao processar a mensagem."},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


app.include_router(health_router)
app.include_router(chats_router)
app.include_router(keys_router)
app.include_router(a2a_router)

# Servidor MCP das tools de domínio, no mesmo processo da API (POST /mcp).
app.mount("/mcp", montar_app_mcp())
