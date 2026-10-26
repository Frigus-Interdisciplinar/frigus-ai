"""
Recursos montados uma vez por processo. Sem `app.state` pros clientes: `chat_service` também
serve a TUI (sem `app`), e os singletons lazy de `infra/` já cumprem o papel. O único uso é o
`guard_decorator` do fastapi-guard (ver `middleware/__init__.py`).
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from guard.lifespan import guard_startup

from frigus_ai.api.mcp import lifespan_mcp
from frigus_ai.graph.builder import fluxo_agentes
from frigus_ai.infra.logging import Logging
from frigus_ai.infra.spoonacular import spoonacular
from frigus_ai.services.chat_service import drenar_tarefas
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.recipe_service import recipe_service

logger = Logging.get_logger(__name__)


async def _parar(tarefa: asyncio.Task[None]) -> None:
    tarefa.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await tarefa


async def _sincronizar_grafo() -> None:
    """Em segundo plano: Neo4j fora do ar não pode impedir a API de subir."""

    try:
        enviadas = await recipe_service.sincronizar_grafo()
        logger.info("Grafo de receitas sincronizado | enviadas=%s", enviadas)
    except Exception:
        logger.exception("Falha ao sincronizar o grafo de receitas")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    await guard_startup(app)

    await fluxo_agentes.get()
    logger.info("Grafo de agentes compilado e checkpointer pronto.")

    reconciliador = asyncio.create_task(chat_service.reconciliar_memoria_loop())
    sincronizacao = asyncio.create_task(_sincronizar_grafo())

    try:
        async with lifespan_mcp():
            yield
    finally:
        await _parar(reconciliador)
        await _parar(sincronizacao)
        await drenar_tarefas()
        await fluxo_agentes.aclose()
        await spoonacular.fechar_async()


__all__ = ["lifespan"]
