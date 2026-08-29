import operator
from typing import Annotated, Literal, get_args

from langgraph.graph import MessagesState

# Literal em vez de StrEnum: os valores viram `str` puro em runtime, então o
# checkpointer (MongoDBSaver) não precisa mais da allowlist de msgpack que o
# StrEnum exigia (LANGGRAPH_ALLOWED_MSGPACK_MODULES, removido de graph/builder.py).
RouteLiteral = Literal[
    "estoque",
    "compras",
    "receitas",
    "faq",
    "financeiro",
    "fim",
    "guardrail_entrada",
    "guardrail_saida",
    "juiz",
]


class Route:
    """Namespace de constantes — não instanciar. Mantém o acesso Route.X, mas
    cada valor já é um `str` puro (sem classe/metaclasse por trás)."""

    ESTOQUE:           RouteLiteral = "estoque"
    COMPRAS:           RouteLiteral = "compras"
    RECEITAS:          RouteLiteral = "receitas"
    FAQ:               RouteLiteral = "faq"
    FINANCEIRO:        RouteLiteral = "financeiro"
    FIM:               RouteLiteral = "fim"
    GUARDRAIL_ENTRADA: RouteLiteral = "guardrail_entrada"
    GUARDRAIL_SAIDA:   RouteLiteral = "guardrail_saida"
    JUIZ:              RouteLiteral = "juiz"


# Conjunto de valores válidos derivado do próprio Literal — usado por
# agents/nodes/router.py pra validar o ROUTE=<algo> que o LLM devolveu,
# no lugar do antigo `Route(valor)` + `except ValueError` do StrEnum.
ROTAS_VALIDAS: frozenset[str] = frozenset(get_args(RouteLiteral))


class Estado(MessagesState):
    resposta_especialista: str
    dados_especialista:    str  # saída crua do especialista (JSON/RAG), preservada mesmo após o Orquestrador reformatar resposta_especialista — usada pelo Juiz para checar grounding
    agentes_chamados:      Annotated[list[str], operator.add]
    rota:                  RouteLiteral
    pergunta_original:     str
    mapa_pii:              dict
    mensagem_bloqueada:    str | None
    perfil_usuario:        str
    stock_id:              int | None

    # Juiz (LLM-as-judge)
    tentativas_juiz:  int
    veredito_juiz:    str
    justificativa_juiz: str
    feedback_juiz:    str
