from frigus_ai.graph.agents import compras_app
from frigus_ai.graph.names import COMPRAS
from frigus_ai.graph.nodes.especialista import especialista_com_agente

no_compras = especialista_com_agente(COMPRAS, compras_app)


__all__ = ["no_compras"]
