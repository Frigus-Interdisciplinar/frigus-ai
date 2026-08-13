import os
os.environ["LANGGRAPH_ALLOWED_MSGPACK_MODULES"] = (
    "frigus_ai.agents.nodes.names,frigus_ai.graph.state"
)

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from frigus_ai.graph.state import Estado, Route

from frigus_ai.agents.nodes.names import NodeName
from frigus_ai.agents.nodes import (
    no_roteador,
    no_estoque,
    no_compras,
    no_receitas,
    no_faq,
    no_financeiro,
    no_orquestrador,
    no_juiz,
    no_guardrail_entrada,
    no_guardrail_saida,
)


def decidir_apos_guardrail_entrada(estado: Estado) -> str:
    if estado.get("mensagem_bloqueada"):
        return Route.FIM
    return NodeName.ROTEADOR


def decidir_especialista(estado: Estado) -> str:
    rota = estado.get("rota", Route.FIM)
    if rota not in (Route.ESTOQUE, Route.COMPRAS, Route.RECEITAS, Route.FAQ, Route.FINANCEIRO):
        return Route.FIM
    return rota


def decidir_apos_juiz(estado: Estado) -> str:
    """
    Se o Juiz reprovou e ainda há tentativas disponíveis (feedback_juiz preenchido
    por no_juiz), volta para o MESMO especialista que originou a rota. Caso
    contrário (aprovado, ou tentativas esgotadas), segue para o Guardrail de Saída.
    """

    if estado.get("feedback_juiz"):
        return estado.get("rota", NodeName.GUARDRAIL_SAIDA)
    return NodeName.GUARDRAIL_SAIDA


grafo = StateGraph(Estado)

grafo.add_node(NodeName.GUARDRAIL_ENTRADA, no_guardrail_entrada)
grafo.add_node(NodeName.ROTEADOR,          no_roteador)
grafo.add_node(NodeName.ESTOQUE,           no_estoque)
grafo.add_node(NodeName.COMPRAS,           no_compras)
grafo.add_node(NodeName.RECEITAS,          no_receitas)
grafo.add_node(NodeName.FAQ,               no_faq)
grafo.add_node(NodeName.FINANCEIRO,        no_financeiro)
grafo.add_node(NodeName.ORQUESTRADOR,      no_orquestrador)
grafo.add_node(NodeName.JUIZ,              no_juiz)
grafo.add_node(NodeName.GUARDRAIL_SAIDA,   no_guardrail_saida)


grafo.set_entry_point(NodeName.GUARDRAIL_ENTRADA)

grafo.add_conditional_edges(
    source   = NodeName.GUARDRAIL_ENTRADA,
    path     = decidir_apos_guardrail_entrada,
    path_map = {
        Route.FIM:         END,
        NodeName.ROTEADOR: NodeName.ROTEADOR,
    },
)

grafo.add_conditional_edges(
    source   = NodeName.ROTEADOR,
    path     = decidir_especialista,
    path_map = {
        Route.ESTOQUE:    NodeName.ESTOQUE,
        Route.COMPRAS:    NodeName.COMPRAS,
        Route.RECEITAS:   NodeName.RECEITAS,
        Route.FAQ:        NodeName.FAQ,
        Route.FINANCEIRO: NodeName.FINANCEIRO,
        Route.FIM:        END,
    },
)

# Estoque/Compras/Financeiro produzem JSON estruturado -> Orquestrador formata em linguagem natural
grafo.add_edge(NodeName.ESTOQUE,    NodeName.ORQUESTRADOR)
grafo.add_edge(NodeName.COMPRAS,    NodeName.ORQUESTRADOR)
grafo.add_edge(NodeName.FINANCEIRO, NodeName.ORQUESTRADOR)
grafo.add_edge(NodeName.ORQUESTRADOR, NodeName.JUIZ)

# Receitas/FAQ já respondem em linguagem natural -> vão direto para o Juiz
grafo.add_edge(NodeName.RECEITAS, NodeName.JUIZ)
grafo.add_edge(NodeName.FAQ,      NodeName.JUIZ)

# Juiz: reprovado + tentativas disponíveis -> volta pro especialista de origem; caso contrário -> Guardrail de Saída
grafo.add_conditional_edges(
    source   = NodeName.JUIZ,
    path     = decidir_apos_juiz,
    path_map = {
        Route.ESTOQUE:              NodeName.ESTOQUE,
        Route.COMPRAS:              NodeName.COMPRAS,
        Route.RECEITAS:             NodeName.RECEITAS,
        Route.FAQ:                  NodeName.FAQ,
        Route.FINANCEIRO:           NodeName.FINANCEIRO,
        NodeName.GUARDRAIL_SAIDA:   NodeName.GUARDRAIL_SAIDA,
    },
)

grafo.add_edge(NodeName.GUARDRAIL_SAIDA, END)


memory = MemorySaver()
fluxo_agentes = grafo.compile(checkpointer=memory)

__all__ = ["fluxo_agentes"]
