from frigus_ai.graph.agents import financeiro_app
from frigus_ai.graph.names import FINANCEIRO
from frigus_ai.graph.nodes.especialista import especialista_com_agente

no_financeiro = especialista_com_agente(FINANCEIRO, financeiro_app)


__all__ = ["no_financeiro"]
