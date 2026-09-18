import operator
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, NotRequired, TypedDict, get_args

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState

from frigus_ai.graph.names import NodeLiteral
from frigus_ai.privacy import MapaPII

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

ROTAS_VALIDAS: frozenset[str] = frozenset(get_args(RouteLiteral))

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


class EntradaGrafo(MessagesState):
    """Único formato aceito ao iniciar um turno — impede injetar campos internos do estado."""

    perfil_usuario: NotRequired[str]
    stock_id:       NotRequired[int | None]


class Estado(MessagesState):
    resposta_especialista: NotRequired[str]
    dados_especialista:    NotRequired[str]  # saída crua do especialista (JSON/RAG), preservada mesmo após o Orquestrador reformatar resposta_especialista — usada pelo Juiz para checar grounding
    agentes_chamados:      NotRequired[Annotated[list[NodeLiteral], operator.add]]
    rota:                  NotRequired[RouteLiteral]
    pergunta_original:     NotRequired[str]
    mapa_pii:              NotRequired[MapaPII]
    mensagem_bloqueada:    NotRequired[str | None]
    perfil_usuario:        NotRequired[str]
    stock_id:              NotRequired[int | None]

    # Juiz (LLM-as-judge)
    tentativas_juiz:    NotRequired[int]
    veredito_juiz:      NotRequired[str]
    justificativa_juiz: NotRequired[str]
    feedback_juiz:      NotRequired[str]


class SaidaGrafo(MessagesState):
    """Único formato devolvido ao chamador — não expõe mapa_pii, perfil, rota etc."""


class RouterUpdate(TypedDict):
    agentes_chamados:  list[NodeLiteral]
    rota:              RouteLiteral
    pergunta_original: str
    tentativas_juiz:   NotRequired[int]
    messages:          NotRequired[list[AnyMessage]]


class EspecialistaUpdate(TypedDict):
    """Estoque/Compras/Financeiro: devolvem JSON cru, o Orquestrador é que escreve pro usuário."""

    agentes_chamados:      list[NodeLiteral]
    resposta_especialista: str
    dados_especialista:    str


class FaqUpdate(TypedDict):
    """FAQ/Receitas: já respondem em linguagem natural, então também publicam em `messages`."""

    agentes_chamados:      list[NodeLiteral]
    messages:              list[AnyMessage]
    resposta_especialista: str
    dados_especialista:    str


class OrquestradorUpdate(TypedDict):
    agentes_chamados:      list[NodeLiteral]
    messages:              list[AnyMessage]
    resposta_especialista: str


class JuizUpdate(TypedDict):
    agentes_chamados:   list[NodeLiteral]
    veredito_juiz:      str
    justificativa_juiz: str
    feedback_juiz:      str
    tentativas_juiz:    NotRequired[int]


class GuardrailEntradaUpdate(TypedDict):
    agentes_chamados:   list[NodeLiteral]
    messages:           list[AnyMessage]
    mensagem_bloqueada: str | None
    mapa_pii:           NotRequired[MapaPII]


class GuardrailSaidaUpdate(TypedDict):
    agentes_chamados: list[NodeLiteral]
    messages:         list[AnyMessage]


# Contrato dos nodes: `Estado -> Awaitable[R]`, R sendo o Update específico de cada node
# (RouterUpdate, EspecialistaUpdate, ...). Não é Protocol de propósito — os nodes de hoje são
# funções puras, sem atributo/método extra que justifique uma classe; Protocol só valeria a pena
# se algum node precisasse carregar estado ou metadado além da própria chamada. Usado em
# `graph/builder.py` pra travar, com mypy, que cada função passada a `add_node()` bate com o
# Update esperado naquele node — sem isso, um builder que troca `no_roteador` por `no_financeiro`
# por engano ainda tipa limpo, porque `add_node()` é permissivo demais nos stubs do LangGraph.
type AsyncNode[R] = Callable[[Estado], Awaitable[R]]


__all__ = [
    "ROTAS_VALIDAS",
    "AsyncNode",
    "EntradaGrafo",
    "EspecialistaUpdate",
    "Estado",
    "FaqUpdate",
    "GuardrailEntradaUpdate",
    "GuardrailSaidaUpdate",
    "JuizUpdate",
    "OrquestradorUpdate",
    "Route",
    "RouteLiteral",
    "RouterUpdate",
    "SaidaGrafo",
]
