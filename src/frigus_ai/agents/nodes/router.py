import re

from config.logging import get_logger
from frigus_ai.agents.nodes.names import NodeName
from frigus_ai.graph.agents import router_app
from frigus_ai.graph.state import Estado, Route

log = get_logger(__name__)


def _extrair_rota(texto: str) -> Route:

    match = re.search(r"ROUTE=(\w+)", texto)
    if not match:
        return Route.FIM

    try:
        return Route(match.group(1))
    except ValueError:
        return Route.FIM


def _extrair_pergunta(texto: str) -> str:

    match = re.search(r"PERGUNTA_ORIGINAL=(.+)", texto)
    if not match:
        return ""

    return match.group(1).strip()


def no_roteador(estado: Estado) -> dict:

    saida = router_app.invoke({"messages": list(estado["messages"])})
    texto = saida["messages"][-1].content
    rota  = _extrair_rota(texto)
    pergunta = _extrair_pergunta(texto)

    log.debug(f"Rota escolhida: {rota} | pergunta: '{pergunta}'")

    if rota is Route.FIM:
        return {
            "agentes_chamados": [NodeName.ROTEADOR],
            "rota":             Route.FIM,
            "pergunta_original": pergunta,
            "messages":         [{"role": "assistant", "content": texto}],
        }

    return {
        "agentes_chamados":  [NodeName.ROTEADOR],
        "rota":              rota,
        "pergunta_original": pergunta,
        "tentativas_juiz":   0,
    }
