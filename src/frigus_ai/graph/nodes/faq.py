from langchain_core.messages import AIMessage

from frigus_ai.evals.metrics import medir_node
from frigus_ai.graph.agents import faq_app
from frigus_ai.graph.names import FAQ
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.state import Estado, FaqUpdate


@medir_node(FAQ)
async def no_faq(estado: Estado) -> FaqUpdate:
    resposta = await responder(faq_app, mensagens_do_turno(estado, apenas_pergunta=True))

    return FaqUpdate(
        agentes_chamados=[FAQ],
        messages=[AIMessage(content=resposta)],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_faq"]
