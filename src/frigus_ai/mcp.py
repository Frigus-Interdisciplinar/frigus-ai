"""Servidor MCP das tools de domínio do Frigus.AI."""

import functools

from mcp.server.mcpserver import MCPServer
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from frigus_ai.api.auth import resolver_usuario
from frigus_ai.graph.tools import (
    COMPRAS_TOOLS,
    ESTOQUE_TOOLS,
    FAQ_TOOLS,
    FINANCEIRO_TOOLS,
    RECEITAS_TOOLS,
)
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.services.user_service import user_service

TOOLS = {
    tool.name: tool
    for tool in [
        *ESTOQUE_TOOLS,
        *COMPRAS_TOOLS,
        *RECEITAS_TOOLS,
        *FINANCEIRO_TOOLS,
        *FAQ_TOOLS,
    ]
}


def _adaptar(tool):
    @functools.wraps(tool.func)
    async def wrapper(**kwargs):
        return await tool.ainvoke(kwargs)

    return wrapper


servidor = MCPServer(name="frigus-ai")

for nome, tool in TOOLS.items():
    servidor.tool(name=nome)(_adaptar(tool))


def identidade_mcp(app: ASGIApp) -> ASGIApp:
    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        user_id = await resolver_usuario(Headers(scope=scope).get("x-api-key"))
        if user_id is None:
            await JSONResponse({"detail": "API key inválida."}, status_code=401)(
                scope, receive, send
            )
            return

        stock_id = await user_service.resolver_stock_id(user_id)
        with session_context(user_id=user_id, stock_id=stock_id):
            await app(scope, receive, send)

    return middleware


_app = servidor.streamable_http_app(streamable_http_path="/", stateless_http=True)


def montar_app() -> ASGIApp:
    return identidade_mcp(_app)


def lifespan_mcp():
    return _app.router.lifespan_context(_app)


__all__ = [
    "TOOLS",
    "identidade_mcp",
    "lifespan_mcp",
    "montar_app",
    "servidor",
    "user_service",
]
