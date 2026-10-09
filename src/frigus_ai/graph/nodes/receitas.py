from langgraph.runtime import Runtime

from frigus_ai.graph.agents import receitas_app
from frigus_ai.graph.names import RECEITAS
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.nodes.especialista import especialista
from frigus_ai.graph.state import ContextoPrompt, Estado


@especialista(RECEITAS)
async def no_receitas(estado: Estado, runtime: Runtime[ContextoPrompt]) -> str:
    return await responder(receitas_app, mensagens_do_turno(estado, apenas_pergunta=True), runtime.context)


__all__ = ["no_receitas"]
