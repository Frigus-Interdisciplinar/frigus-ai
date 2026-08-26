from typing import Literal

# Literal em vez de StrEnum: os valores viram `str` puro em runtime, então o
# checkpointer (MongoDBSaver) não precisa mais da allowlist de msgpack que o
# StrEnum exigia — Estado passa a guardar só tipos nativos (str/dict/int/list[str]).
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


class Node:
    """Namespace de constantes — não instanciar. Mantém o acesso Node.X, mas
    cada valor já é um `str` puro (sem classe/metaclasse por trás)."""

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


__all__ = ["Node", "NodeLiteral"]
