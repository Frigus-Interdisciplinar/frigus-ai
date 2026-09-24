import operator
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, NotRequired, TypedDict, get_args

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

from frigus_ai.graph.names import NodeLiteral
from frigus_ai.graph.tools.estoque.schemas import Category, StoragePlace
from frigus_ai.privacy import MapaPII

type AsyncNode[R] = Callable[[Estado], Awaitable[R]]

RotaEspecialista = Literal["estoque", "compras", "receitas", "faq", "financeiro", "assessor"]
RotaRoteador     = Literal[RotaEspecialista, "fim"]
RouteLiteral     = Literal[RotaRoteador, "visao", "guardrail_entrada", "guardrail_saida", "juiz"]

ROTAS_VALIDAS: frozenset[str] = frozenset(get_args(RouteLiteral))


class Route:
    """Namespace de constantes — não instanciar. Mantém o acesso Route.X, mas
    cada valor já é um `str` puro (sem classe/metaclasse por trás)."""

    ESTOQUE:           RouteLiteral = "estoque"
    COMPRAS:           RouteLiteral = "compras"
    RECEITAS:          RouteLiteral = "receitas"
    FAQ:               RouteLiteral = "faq"
    FINANCEIRO:        RouteLiteral = "financeiro"
    ASSESSOR:          RouteLiteral = "assessor"
    FIM:               RouteLiteral = "fim"
    VISAO:             RouteLiteral = "visao"
    GUARDRAIL_ENTRADA: RouteLiteral = "guardrail_entrada"
    GUARDRAIL_SAIDA:   RouteLiteral = "guardrail_saida"
    JUIZ:              RouteLiteral = "juiz"


class Roteamento(BaseModel):
    """Saída estruturada do roteador (`response_format` do `router_app`)."""

    rota: RotaRoteador
    resposta: str = Field(
        default="",
        description=(
            "Só quando rota=fim: o texto para o usuário (saudação, fora de escopo ou "
            "pedido de clarificação). Vazio quando encaminha pra um especialista."
        ),
    )


class EntradaGrafo(MessagesState):
    """Único formato aceito ao iniciar um turno — impede injetar campos internos do estado."""

    stock_id:       NotRequired[int | None]
    imagem_b64:     NotRequired[str]


class Estado(MessagesState):
    resposta_especialista: NotRequired[str]
    dados_especialista:    NotRequired[str]  # saída crua do especialista (JSON/RAG), preservada mesmo após o Orquestrador reformatar resposta_especialista — usada pelo Juiz para checar grounding
    agentes_chamados:      NotRequired[Annotated[list[NodeLiteral], operator.add]]
    rota:                  NotRequired[RouteLiteral]
    pergunta_original:     NotRequired[str]
    mapa_pii:              NotRequired[MapaPII]
    mensagem_bloqueada:    NotRequired[str | None]
    stock_id:              NotRequired[int | None]
    imagem_b64:            NotRequired[str]

    # Juiz (LLM-as-judge)
    tentativas_juiz:    NotRequired[int]
    veredito_juiz:      NotRequired[str]
    justificativa_juiz: NotRequired[str]
    feedback_juiz:      NotRequired[str]


class SaidaGrafo(MessagesState):
    """Único formato devolvido ao chamador — não expõe mapa_pii, rota etc."""


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


class VisaoUpdate(EspecialistaUpdate):
    """Visão seta a própria rota: o roteador não roda em turno com foto, e sem `rota` o
    Juiz não teria pra onde devolver uma resposta reprovada."""

    rota: RouteLiteral


class FaqUpdate(TypedDict):
    """FAQ/Receitas: já respondem em linguagem natural, então também publicam em `messages`."""

    agentes_chamados:      list[NodeLiteral]
    messages:              list[AnyMessage]
    resposta_especialista: str
    dados_especialista:    str


class AssessorUpdate(FaqUpdate):
    """Assessor (A2A): texto pronto vindo de outro agente, publicado direto como FAQ/Receitas.
    `dados_especialista` vazio = Assessor indisponível (ver `decidir_apos_assessor`)."""


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


class ItemIdentificado(BaseModel):
    """Um item que a Visão (`graph/nodes/visao.py`) reconheceu numa foto. `category`/
    `storage_place` reaproveitam os `Literal` de `graph/tools/estoque/schemas.py` —
    os MESMOS valores que `POST /stock/items` aceita. Como o `with_structured_output`
    vira function-calling/JSON-schema pro provider, o modelo fica proibido de emitir
    um valor fora da lista (não é checagem depois, é restrição na própria geração)."""

    product_name: str = Field(description="Nome do produto (ex.: 'Leite integral').")
    quantity: float = Field(description="Quantidade estimada (ex.: 3, 0.5, 500).")
    unit: str = Field(description="Unidade da quantidade (ex.: 'un', 'kg', 'litro', 'g').")
    category: Category
    storage_place: StoragePlace
    expiring_soon: bool = Field(default=False, description="Parece perto do vencimento pela aparência.")


class InventarioGeladeira(BaseModel):
    items: list[ItemIdentificado]
    confidence: float = Field(description="Confiança geral da identificação, de 0.0 a 1.0.")





__all__ = [
    "ROTAS_VALIDAS",
    "AssessorUpdate",
    "AsyncNode",
    "EntradaGrafo",
    "EspecialistaUpdate",
    "Estado",
    "FaqUpdate",
    "GuardrailEntradaUpdate",
    "GuardrailSaidaUpdate",
    "InventarioGeladeira",
    "ItemIdentificado",
    "JuizUpdate",
    "OrquestradorUpdate",
    "RotaEspecialista",
    "RotaRoteador",
    "Roteamento",
    "Route",
    "RouteLiteral",
    "RouterUpdate",
    "SaidaGrafo",
    "VisaoUpdate",
]
