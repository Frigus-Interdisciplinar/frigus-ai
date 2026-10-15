from frigus_ai.graph.agents import estoque_app
from frigus_ai.graph.names import ESTOQUE
from frigus_ai.graph.nodes.contexto import (
    contexto_do_estado,
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import EspecialistaUpdate, Estado
from frigus_ai.telemetry import medir_node
from frigus_ai.graph.nodes.especialista import especialista_com_agente

no_estoque = especialista_com_agente(ESTOQUE, estoque_app)


__all__ = ["no_estoque"]
