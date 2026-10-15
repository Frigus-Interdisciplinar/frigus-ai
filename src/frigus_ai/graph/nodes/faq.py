from frigus_ai.graph.agents import faq_app
from frigus_ai.graph.names import FAQ
from frigus_ai.graph.nodes.contexto import (
    contexto_do_estado,
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import Estado, FaqUpdate
from frigus_ai.telemetry import medir_node


@medir_node(FAQ)
async def no_faq(estado: Estado) -> FaqUpdate:
    resposta = await responder(
        faq_app, mensagens_do_turno(estado, apenas_pergunta=True), contexto_do_estado(estado)
    )
from frigus_ai.graph.nodes.especialista import especialista_com_agente

no_faq = especialista_com_agente(FAQ, faq_app)


__all__ = ["no_faq"]
