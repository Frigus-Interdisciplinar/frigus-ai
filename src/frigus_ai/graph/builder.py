from functools import cache

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, StateGraph

from frigus_ai.agents.nodes import (
    no_compras,
    no_estoque,
    no_faq,
    no_financeiro,
    no_guardrail_entrada,
    no_guardrail_saida,
    no_juiz,
    no_orquestrador,
    no_receitas,
    no_roteador,
)
from frigus_ai.agents.nodes.names import Node
from frigus_ai.graph.state import Estado, Route
from frigus_ai.tools.mongo.connection import banco


def decidir_apos_guardrail_entrada(estado: Estado) -> str:
    if estado.get("mensagem_bloqueada"):
        return Route.FIM
    return Node.ROTEADOR


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
        return estado.get("rota", Node.GUARDRAIL_SAIDA)
    return Node.GUARDRAIL_SAIDA


grafo = StateGraph(Estado)

grafo.add_node(Node.GUARDRAIL_ENTRADA, no_guardrail_entrada)
grafo.add_node(Node.ROTEADOR,          no_roteador)
grafo.add_node(Node.ESTOQUE,           no_estoque)
grafo.add_node(Node.COMPRAS,           no_compras)
grafo.add_node(Node.RECEITAS,          no_receitas)
grafo.add_node(Node.FAQ,               no_faq)
grafo.add_node(Node.FINANCEIRO,        no_financeiro)
grafo.add_node(Node.ORQUESTRADOR,      no_orquestrador)
grafo.add_node(Node.JUIZ,              no_juiz)
grafo.add_node(Node.GUARDRAIL_SAIDA,   no_guardrail_saida)


grafo.set_entry_point(Node.GUARDRAIL_ENTRADA)

grafo.add_conditional_edges(
    source   = Node.GUARDRAIL_ENTRADA,
    path     = decidir_apos_guardrail_entrada,
    path_map = {
        Route.FIM:         END,
        Node.ROTEADOR: Node.ROTEADOR,
    },
)

grafo.add_conditional_edges(
    source   = Node.ROTEADOR,
    path     = decidir_especialista,
    path_map = {
        Route.ESTOQUE:    Node.ESTOQUE,
        Route.COMPRAS:    Node.COMPRAS,
        Route.RECEITAS:   Node.RECEITAS,
        Route.FAQ:        Node.FAQ,
        Route.FINANCEIRO: Node.FINANCEIRO,
        Route.FIM:        END,
    },
)

# Estoque/Compras/Financeiro produzem JSON estruturado -> Orquestrador formata em linguagem natural
grafo.add_edge(Node.ESTOQUE,    Node.ORQUESTRADOR)
grafo.add_edge(Node.COMPRAS,    Node.ORQUESTRADOR)
grafo.add_edge(Node.FINANCEIRO, Node.ORQUESTRADOR)
grafo.add_edge(Node.ORQUESTRADOR, Node.JUIZ)

# Receitas/FAQ já respondem em linguagem natural -> vão direto para o Juiz
grafo.add_edge(Node.RECEITAS, Node.JUIZ)
grafo.add_edge(Node.FAQ,      Node.JUIZ)

# Juiz: reprovado + tentativas disponíveis -> volta pro especialista de origem; caso contrário -> Guardrail de Saída
grafo.add_conditional_edges(
    source   = Node.JUIZ,
    path     = decidir_apos_juiz,
    path_map = {
        Route.ESTOQUE:              Node.ESTOQUE,
        Route.COMPRAS:              Node.COMPRAS,
        Route.RECEITAS:             Node.RECEITAS,
        Route.FAQ:                  Node.FAQ,
        Route.FINANCEIRO:           Node.FINANCEIRO,
        Node.GUARDRAIL_SAIDA:   Node.GUARDRAIL_SAIDA,
    },
)

grafo.add_edge(Node.GUARDRAIL_SAIDA, END)


@cache
def fluxo_agentes():
    """
    Compila o grafo sob demanda. Lazy porque o MongoDBSaver abre conexão com o
    Mongo — nada de I/O no import do módulo (mesma regra das demais conexões).
    """

    checkpointer = MongoDBSaver(
        banco.client,
        db_name=banco.name,
        checkpoint_collection_name="graph_checkpoints",
        writes_collection_name="graph_checkpoint_writes",
    )
    return grafo.compile(checkpointer=checkpointer)


__all__ = ["fluxo_agentes"]
