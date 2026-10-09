from langgraph.runtime import Runtime

from frigus_ai.graph.agents import estoque_app
from frigus_ai.graph.names import ESTOQUE
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.nodes.especialista import especialista
from frigus_ai.graph.state import ContextoPrompt, Estado


@especialista(ESTOQUE)
async def no_estoque(estado: Estado, runtime: Runtime[ContextoPrompt]) -> str:
    return await responder(estoque_app, mensagens_do_turno(estado), runtime.context)


__all__ = ["no_estoque"]
