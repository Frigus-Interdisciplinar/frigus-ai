from langgraph.runtime import Runtime

from frigus_ai.graph.agents import financeiro_app
from frigus_ai.graph.names import FINANCEIRO
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.nodes.especialista import especialista
from frigus_ai.graph.state import ContextoPrompt, Estado


@especialista(FINANCEIRO)
async def no_financeiro(estado: Estado, runtime: Runtime[ContextoPrompt]) -> str:
    return await responder(financeiro_app, mensagens_do_turno(estado), runtime.context)


__all__ = ["no_financeiro"]
