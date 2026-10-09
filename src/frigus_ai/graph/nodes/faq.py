from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from frigus_ai.graph.agents import faq_app
from frigus_ai.graph.names import FAQ
from frigus_ai.graph.nodes.contexto import (
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import ContextoPrompt, Estado, FaqUpdate
from frigus_ai.telemetry import medir_node


@medir_node(FAQ)
async def no_faq(estado: Estado, runtime: Runtime[ContextoPrompt]) -> FaqUpdate:
    resposta = await responder(
        faq_app, mensagens_do_turno(estado, apenas_pergunta=True), runtime.context
    )

    return FaqUpdate(
        agentes_chamados=[FAQ],
        messages=[AIMessage(content=resposta)],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_faq"]
