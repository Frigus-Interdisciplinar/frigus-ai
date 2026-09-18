import re

from langchain_core.messages import AIMessage

from frigus_ai.evals.metrics import ROUTER_DECISIONS, medir_node
from frigus_ai.graph.agents import router_app
from frigus_ai.graph.names import ROTEADOR
from frigus_ai.graph.nodes.contexto import responder
from frigus_ai.graph.state import (
    ROTAS_VALIDAS,
    Estado,
    Route,
    RouteLiteral,
    RouterUpdate,
)
from frigus_ai.logging import Logging

log = Logging.get_logger(__name__)


def _extrair_rota(texto: str) -> RouteLiteral:

    match = re.search(r"ROUTE=(\w+)", texto)
    if not match:
        return Route.FIM

    valor = match.group(1)
    return valor if valor in ROTAS_VALIDAS else Route.FIM  # type: ignore[return-value]


def _extrair_pergunta(texto: str) -> str:

    match = re.search(r"PERGUNTA_ORIGINAL=(.+)", texto)
    if not match:
        return ""

    return match.group(1).strip()


@medir_node(ROTEADOR)
async def no_roteador(estado: Estado) -> RouterUpdate:

    texto    = await responder(router_app, estado["messages"])
    rota     = _extrair_rota(texto)
    pergunta = _extrair_pergunta(texto)

    log.debug(f"Rota escolhida: {rota} | pergunta: '{pergunta}'")
    ROUTER_DECISIONS.labels(route=rota).inc()

    if rota == Route.FIM:
        return RouterUpdate(
            agentes_chamados=[ROTEADOR],
            rota=Route.FIM,
            pergunta_original=pergunta,
            messages=[AIMessage(content=texto)],
        )

    return RouterUpdate(
        agentes_chamados=[ROTEADOR],
        rota=rota,
        pergunta_original=pergunta,
        tentativas_juiz=0,
    )


__all__ = ["no_roteador"]
