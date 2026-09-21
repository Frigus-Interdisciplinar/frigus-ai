"""
Recursos que a API monta uma vez por processo. É o único lugar da camada `api/` que abre e fecha
infra — o que já tem ciclo de vida próprio (pool do Postgres em `infra/postgres/connection.py`,
cliente do Mongo, do Redis e do Qdrant) continua lazy e não é duplicado aqui.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from frigus_ai.graph.builder import fluxo_agentes
from frigus_ai.graph.tools.spoonacular.connection import fechar_client
from frigus_ai.logging import Logging
from frigus_ai.mcp import lifespan_mcp

logger = Logging.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Compila o grafo aqui, e não na primeira mensagem: o Mongo fora do ar derruba o
    # startup, em vez de aceitar tráfego e errar 502 em cada mensagem.
    await fluxo_agentes.get()
    logger.info("Grafo de agentes compilado e checkpointer pronto.")

    # `lifespan_mcp` inicializa o task group do sub-app MCP montado — sem encadear
    # aqui, toda chamada em /mcp morre em "Task group is not initialized".
    async with lifespan_mcp():
        yield

    await fluxo_agentes.aclose()
    # httpx.Client segura o pool de conexões; sem isso o shutdown deixa socket
    # aberto (e o pytest reclama de recurso não fechado).
    await fechar_client()


__all__ = ["lifespan"]
