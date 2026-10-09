from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from frigus_ai.graph.agents import orquestrador_app
from frigus_ai.graph.names import ORQUESTRADOR
from frigus_ai.graph.nodes.contexto import responder
from frigus_ai.graph.state import ContextoPrompt, Estado, OrquestradorUpdate
from frigus_ai.telemetry import medir_node


@medir_node(ORQUESTRADOR)
async def no_orquestrador(estado: Estado, runtime: Runtime[ContextoPrompt]) -> OrquestradorUpdate:
    mensagens = [
        *estado["messages"],
        HumanMessage(content=estado["resposta_especialista"]),
    ]

    resposta = await responder(orquestrador_app, mensagens, runtime.context)

    return OrquestradorUpdate(
        agentes_chamados=[ORQUESTRADOR],
        resposta_especialista=resposta,
    )


__all__ = ["no_orquestrador"]
