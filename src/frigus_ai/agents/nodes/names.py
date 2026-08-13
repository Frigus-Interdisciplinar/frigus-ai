from enum import StrEnum


class NodeName(StrEnum):
    ROTEADOR =          "roteador_node"
    ESTOQUE =           "estoque_node"
    COMPRAS =           "compras_node"
    RECEITAS =          "receitas_node"
    FAQ =               "faq_node"
    FINANCEIRO =        "financeiro_node"
    ORQUESTRADOR =      "orquestrador_node"
    JUIZ =              "juiz_node"
    GUARDRAIL_ENTRADA = "guardrail_entrada_node"
    GUARDRAIL_SAIDA =   "guardrail_saida_node"


__all__ = ["NodeName"]
