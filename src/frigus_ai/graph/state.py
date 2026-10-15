import operator
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Literal, NotRequired, TypedDict, get_args

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from langgraph.runtime import Runtime
from langgraph.types import Overwrite
from pydantic import BaseModel, Field

from frigus_ai.domain.models import Fatos
from frigus_ai.domain.privacy import MapaPII
from frigus_ai.graph.names import NodeLiteral
from frigus_ai.graph.tools.estoque.schemas import Category, StoragePlace

type AsyncNode[R] = Callable[[Estado], Awaitable[R]]
# O LangGraph injeta o `Runtime` pelo NOME do parâmetro (`runtime`), não pela posição.
type AsyncNodeComContexto[R] = Callable[[Estado, Runtime[ContextoPrompt]], Awaitable[R]]

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

    especialistas: list[RotaEspecialista] = Field(
        default_factory=list,
        description="Os domínios que precisam atender o pedido; vazia quando você mesmo responde.",
    )
    resposta: str = Field(
        default="",
        description=(
            "Só com `especialistas` vazia: o texto para o usuário (saudação, fora de escopo ou "
            "pedido de clarificação). Vazio quando encaminha pra algum especialista."
        ),
    )


@dataclass(frozen=True)
class ContextoPrompt:
    """Contexto de runtime do grafo e dos agentes (`context_schema`), carregado pelo runner uma
    vez por turno e passado por `context=` — fica fora do checkpoint, então perfil que falhou ao
    carregar não reaproveita o do turno anterior. Vira seção do system prompt em `dynamic_prompt`.
    Nunca guarda nada de permissão — escopo é ContextVar."""

    fatos:     Fatos | None = None
    conversas: tuple[str, ...] = ()


class EntradaGrafo(MessagesState):
    """Único formato aceito ao iniciar um turno — impede injetar campos internos do estado."""

    stock_id:             NotRequired[int | None]
    imagem_b64:           NotRequired[str]


class ResultadoEspecialista(TypedDict):
    """O que um especialista devolveu no turno. `dados` é o que o Juiz confere (vazio = o
    especialista estava indisponível e `resposta` é só o aviso)."""

    agente:   NodeLiteral
    resposta: str
    dados:    str


class Estado(MessagesState):
    pergunta_original:     NotRequired[str]
    mapa_pii:              NotRequired[MapaPII]
    mensagem_bloqueada:    NotRequired[str | None]
    stock_id:              NotRequired[int | None]
    imagem_b64:            NotRequired[str]

    # Vazia quando o roteador respondeu direto.
    especialistas:         NotRequired[list[RotaEspecialista]]

    # Um item por especialista; o reducer soma os paralelos e o guardrail de entrada zera a cada turno.
    dados_especialistas:   NotRequired[Annotated[list[ResultadoEspecialista], operator.add]]

    resposta_especialista: NotRequired[str]

    # O que o Juiz confere: preservado mesmo depois que o orquestrador reescreve a resposta.
    dados_especialista:    NotRequired[str]

    reescritas_juiz:       NotRequired[int]
    veredito_juiz:         NotRequired[str]
    justificativa_juiz:    NotRequired[str]
    feedback_juiz:         NotRequired[str]


class SaidaGrafo(MessagesState):
    """Único formato devolvido ao chamador — não expõe mapa_pii, especialistas etc."""

    # O runner distingue turno bloqueado pelo guardrail (não é erro) de turno resolvido.
    mensagem_bloqueada: NotRequired[str | None]


class RouterUpdate(TypedDict):
    especialistas: list[RotaEspecialista]
    messages:      NotRequired[list[AnyMessage]]


class ConteudoEspecialista(TypedDict):
    """Retorno de especialista cuja resposta ao usuário difere dos dados que o Juiz confere."""

    resposta: str
    dados:    str


class EspecialistaUpdate(TypedDict):
    """Montado só pelo decorator `@especialista` (`graph/nodes/especialista.py`). A lista de um
    item é somada às dos outros especialistas do turno pelo reducer."""

    dados_especialistas: list[ResultadoEspecialista]


class OrquestradorUpdate(TypedDict):
    resposta_especialista: str
    dados_especialista:    str


class JuizUpdate(TypedDict):
    veredito_juiz:      str
    justificativa_juiz: str
    feedback_juiz:      str
    reescritas_juiz:    NotRequired[int]


class GuardrailEntradaUpdate(TypedDict):
    messages:            list[AnyMessage]
    mensagem_bloqueada:  str | None
    mapa_pii:            NotRequired[MapaPII]
    pergunta_original:   NotRequired[str]

    # Zera o que o turno anterior deixou no checkpoint. Fica aqui, e não no roteador, porque o
    # turno com foto pula o roteador.
    dados_especialistas: NotRequired[Overwrite]
    reescritas_juiz:     NotRequired[int]
    feedback_juiz:       NotRequired[str]


class GuardrailSaidaUpdate(TypedDict):
    messages: list[AnyMessage]


class ItemIdentificado(BaseModel):
    """Um item que a Visão reconheceu numa foto. `category`/`storage_place` são os mesmos
    `Literal` que `POST /stock/items` aceita: no structured output o modelo não consegue
    emitir valor fora da lista."""

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
    "AsyncNode",
    "AsyncNodeComContexto",
    "ConteudoEspecialista",
    "ContextoPrompt",
    "EntradaGrafo",
    "EspecialistaUpdate",
    "Estado",
    "GuardrailEntradaUpdate",
    "GuardrailSaidaUpdate",
    "InventarioGeladeira",
    "ItemIdentificado",
    "JuizUpdate",
    "OrquestradorUpdate",
    "ResultadoEspecialista",
    "RotaEspecialista",
    "RotaRoteador",
    "Roteamento",
    "Route",
    "RouteLiteral",
    "RouterUpdate",
    "SaidaGrafo",
]
