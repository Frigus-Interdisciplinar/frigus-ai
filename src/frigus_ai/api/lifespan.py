"""
Recursos que a API monta uma vez por processo. É o único lugar da camada `api/` que abre e fecha
infra — o que já tem ciclo de vida próprio (pool do Postgres em `infra/postgres/connection.py`,
cliente do Mongo, do Redis e do Qdrant) continua lazy e não é duplicado aqui.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from frigus_ai.graph.builder import fluxo_agentes
from frigus_ai.infra.spoonacular.connection import spoonacular
from frigus_ai.logging import Logging
from frigus_ai.mcp import lifespan_mcp

logger = Logging.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    await fluxo_agentes.get()
    logger.info("Grafo de agentes compilado e checkpointer pronto.")

    async with lifespan_mcp():
        yield

    await fluxo_agentes.aclose()
    await spoonacular.fechar_async()


__all__ = ["lifespan"]
