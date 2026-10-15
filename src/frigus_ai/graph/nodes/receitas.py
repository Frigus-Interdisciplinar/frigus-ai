from frigus_ai.graph.agents import receitas_app
from frigus_ai.graph.names import RECEITAS
from frigus_ai.graph.nodes.contexto import (
    contexto_do_estado,
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import Estado, FaqUpdate
from frigus_ai.telemetry import medir_node


@medir_node(RECEITAS)
async def no_receitas(estado: Estado) -> FaqUpdate:
    resposta = await responder(
        receitas_app, mensagens_do_turno(estado, apenas_pergunta=True), contexto_do_estado(estado)
    )
from frigus_ai.graph.nodes.especialista import especialista_com_agente

no_receitas = especialista_com_agente(RECEITAS, receitas_app)


__all__ = ["no_receitas"]
