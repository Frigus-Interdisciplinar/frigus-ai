"""
Nomes dos nodes registrados no `StateGraph`. Fica em `graph/`, e não em `graph/nodes/`, porque
`graph/state.py` precisa do `NodeLiteral` pra tipar `agentes_chamados`: importar de dentro do
pacote `nodes` executaria `nodes/__init__.py`, que importa todos os nodes, que importam `state` —
`import frigus_ai.graph.state` sozinho morria com ImportError de ciclo.
"""

from typing import Literal

NodeLiteral = Literal[
    "roteador_node",
    "estoque_node",
    "compras_node",
    "receitas_node",
    "faq_node",
    "financeiro_node",
    "orquestrador_node",
    "juiz_node",
    "guardrail_entrada_node",
    "guardrail_saida_node",
]

ROTEADOR:          NodeLiteral = "roteador_node"
ESTOQUE:           NodeLiteral = "estoque_node"
COMPRAS:           NodeLiteral = "compras_node"
RECEITAS:          NodeLiteral = "receitas_node"
FAQ:               NodeLiteral = "faq_node"
FINANCEIRO:        NodeLiteral = "financeiro_node"
ORQUESTRADOR:      NodeLiteral = "orquestrador_node"
JUIZ:              NodeLiteral = "juiz_node"
GUARDRAIL_ENTRADA: NodeLiteral = "guardrail_entrada_node"
GUARDRAIL_SAIDA:   NodeLiteral = "guardrail_saida_node"


__all__ = [
    "COMPRAS",
    "ESTOQUE",
    "FAQ",
    "FINANCEIRO",
    "GUARDRAIL_ENTRADA",
    "GUARDRAIL_SAIDA",
    "JUIZ",
    "ORQUESTRADOR",
    "RECEITAS",
    "ROTEADOR",
    "NodeLiteral",
]
