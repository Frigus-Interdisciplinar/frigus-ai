from langgraph.runtime import Runtime

from frigus_ai.graph.agents import compras_app
from frigus_ai.graph.names import COMPRAS
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.nodes.especialista import especialista
from frigus_ai.graph.state import ContextoPrompt, Estado


@especialista(COMPRAS)
async def no_compras(estado: Estado, runtime: Runtime[ContextoPrompt]) -> str:
    return await responder(compras_app, mensagens_do_turno(estado), runtime.context)


__all__ = ["no_compras"]
