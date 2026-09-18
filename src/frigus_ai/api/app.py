from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from frigus_ai.api.exception_handler import register_exception_handlers
from frigus_ai.api.lifespan import lifespan
from frigus_ai.api.middleware import adicionar_middleware
from frigus_ai.api.routes import a2a_router, chats_router, health_router, keys_router
from frigus_ai.api.routes.mcp import montar_app as montar_app_mcp

app = FastAPI(
    title="Frigus.AI",
    description="API do assistente conversacional do Frigus",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)
adicionar_middleware(app)

app.include_router(health_router)
app.include_router(a2a_router)
app.include_router(chats_router)
app.include_router(keys_router)

# Servidor MCP das tools de domínio, no mesmo processo da API (POST /mcp).
app.mount("/mcp", montar_app_mcp())


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
