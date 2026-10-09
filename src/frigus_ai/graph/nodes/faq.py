from frigus_ai.graph.agents import faq_app
from frigus_ai.graph.names import FAQ
from frigus_ai.graph.nodes.especialista import especialista_com_agente

no_faq = especialista_com_agente(FAQ, faq_app)


__all__ = ["no_faq"]
