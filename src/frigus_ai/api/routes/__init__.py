from fastapi import FastAPI

from frigus_ai.api.mcp import montar_app as montar_app_mcp

from .a2a import router as a2a_router
from .auth import router as auth_router
from .health import router as health_router
from .metrics import router as metrics_router
from .v1 import v1_router


def register_routes(app: FastAPI) -> None:
    # Infra, auth e A2A (agent card no caminho da spec) ficam fora do /v1: contrato próprio.
    for router in (health_router, metrics_router, auth_router, a2a_router, v1_router):
        app.include_router(router)

    # Servidor MCP das tools de domínio, no mesmo processo da API (POST /mcp).
    app.mount("/mcp", montar_app_mcp())


__all__ = ["register_routes"]
