from frigus_ai.graph.agents import estoque_app
from frigus_ai.graph.names import ESTOQUE
from frigus_ai.graph.nodes.especialista import especialista_com_agente

no_estoque = especialista_com_agente(ESTOQUE, estoque_app)


__all__ = ["no_estoque"]
