from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from frigus_ai.graph.agents import receitas_app
from frigus_ai.graph.names import RECEITAS
from frigus_ai.graph.nodes.contexto import (
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import ContextoPrompt, Estado, FaqUpdate
from frigus_ai.telemetry import medir_node


@medir_node(RECEITAS)
async def no_receitas(estado: Estado, runtime: Runtime[ContextoPrompt]) -> FaqUpdate:
    resposta = await responder(
        receitas_app, mensagens_do_turno(estado, apenas_pergunta=True), runtime.context
    )

    return FaqUpdate(
        agentes_chamados=[RECEITAS],
        messages=[AIMessage(content=resposta)],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_receitas"]
