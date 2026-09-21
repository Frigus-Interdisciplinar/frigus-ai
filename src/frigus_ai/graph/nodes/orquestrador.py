from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.graph.agents import orquestrador_app
from frigus_ai.graph.names import ORQUESTRADOR
from frigus_ai.graph.nodes.contexto import responder
from frigus_ai.graph.state import Estado, OrquestradorUpdate
from frigus_ai.observability.metrics import medir_node


@medir_node(ORQUESTRADOR)
async def no_orquestrador(estado: Estado) -> OrquestradorUpdate:
    mensagens = [
        *estado["messages"],
        HumanMessage(content=estado["resposta_especialista"]),
    ]

    resposta = await responder(orquestrador_app, mensagens)

    return OrquestradorUpdate(
        agentes_chamados=[ORQUESTRADOR],
        messages=[AIMessage(content=resposta)],
        resposta_especialista=resposta,
    )


__all__ = ["no_orquestrador"]
