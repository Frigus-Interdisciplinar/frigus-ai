from frigus_ai.graph.agents import receitas_app
from frigus_ai.graph.names import RECEITAS
from frigus_ai.graph.nodes.especialista import especialista_com_agente

no_receitas = especialista_com_agente(RECEITAS, receitas_app)


__all__ = ["no_receitas"]
