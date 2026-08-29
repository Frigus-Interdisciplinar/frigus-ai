"""
Servidor MCP: as mesmas tools de domínio que o grafo usa, expostas pra hosts MCP
externos (Claude Desktop etc.) sem passar pelo grafo inteiro.

Montado dentro da API que já existe, não como processo à parte — assim reaproveita
o `X-API-Key` que já resolve `user_id` nas rotas de chat. As tools de Postgres nunca
recebem `user_id`/`stock_id` como argumento (ver `tools/postgres/context.py`); quem
preenche isso é `identidade_mcp`, o middleware ASGI daqui.
"""

import asyncio
import functools

from mcp.server.mcpserver import MCPServer
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from frigus_ai.chat.service import resolver_stock_id
from frigus_ai.tools import (
    COMPRAS_TOOLS,
    ESTOQUE_TOOLS,
    FAQ_TOOLS,
    FINANCEIRO_TOOLS,
    RECEITAS_TOOLS,
)
from frigus_ai.tools.postgres.context import session_context
from interfaces.api.auth import resolver_usuario

TOOLS = {
    t.name: t
    for t in [
        *ESTOQUE_TOOLS, 
        *COMPRAS_TOOLS, 
        *RECEITAS_TOOLS, 
        *FINANCEIRO_TOOLS, 
        *FAQ_TOOLS
    ]
}


def _adaptar(tool):
    """
    Expõe a tool do LangChain como função simples pro MCP.

    `tool.invoke(kwargs)` em vez de chamar `tool.func` direto: é o que roda o
    `args_schema` (com os validators de `delta`/`novo_valor`, status, YYYY-MM) antes
    da função. O `functools.wraps` empresta a assinatura da função original, que é de
    onde o MCP deriva o JSON Schema da tool.

    ponytail: o schema do MCP sai sem a descrição por campo (ela vive no
    `args_schema`, e o SDK só lê anotação de assinatura). A descrição da tool — que é
    o que guia o host — vem do docstring e é preservada.
    """

    @functools.wraps(tool.func)
    def wrapper(**kwargs):
        return tool.invoke(kwargs)

    return wrapper


servidor = MCPServer(name="frigus-ai")

for nome, tool in TOOLS.items():
    servidor.tool(name=nome)(_adaptar(tool))


def identidade_mcp(app: ASGIApp) -> ASGIApp:
    """
    Resolve `user_id`/`stock_id` pelo `X-API-Key` e abre o `session_context` em volta
    da requisição inteira — é o equivalente ao que `chat/runner.py` faz por turno.

    Fica em middleware ASGI porque o app do MCP é montado (`app.mount`), e sub-app
    montado não executa as dependências do FastAPI.
    """

    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        api_key = Headers(scope=scope).get("x-api-key")
        user_id = resolver_usuario(api_key)

        if user_id is None:
            await JSONResponse({"detail": "API key inválida."}, status_code=401)(scope, receive, send)
            return

        stock_id = await asyncio.to_thread(resolver_stock_id, user_id)

        with session_context(user_id=user_id, stock_id=stock_id):
            await app(scope, receive, send)

    return middleware


_app_mcp = servidor.streamable_http_app(streamable_http_path="/", stateless_http=True)


def montar_app() -> ASGIApp:
    return identidade_mcp(_app_mcp)


def lifespan_mcp():
    """
    O gerenciador de sessão do SDK só inicializa o task group dentro do próprio
    lifespan, e app montado com `app.mount()` não tem o lifespan executado pelo
    FastAPI — sem encadear isto, toda chamada morre em "Task group is not
    initialized".
    """

    return _app_mcp.router.lifespan_context(_app_mcp)
