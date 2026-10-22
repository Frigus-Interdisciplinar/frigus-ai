import asyncio
from collections.abc import Mapping

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from frigus_ai.graph.guardrail.entrada import no_guardrail_entrada
from frigus_ai.graph.guardrail.saida import no_guardrail_saida
from frigus_ai.graph.names import (
    A2A_ASSESSOR,
    COMPRAS,
    ESTOQUE,
    FAQ,
    FINANCEIRO,
    GUARDRAIL_ENTRADA,
    GUARDRAIL_SAIDA,
    JUIZ,
    ORQUESTRADOR,
    RECEITAS,
    ROTEADOR,
    VISAO,
    NodeLiteral,
)
from frigus_ai.graph.nodes import (
    no_assessor,
    no_compras,
    no_estoque,
    no_faq,
    no_financeiro,
    no_juiz,
    no_orquestrador,
    no_receitas,
    no_roteador,
    no_visao,
)
from frigus_ai.graph.state import (
    AsyncNode,
    AsyncNodeComContexto,
    ContextoPrompt,
    EntradaGrafo,
    EspecialistaUpdate,
    Estado,
    GuardrailEntradaUpdate,
    GuardrailSaidaUpdate,
    JuizUpdate,
    OrquestradorUpdate,
    RotaEspecialista,
    Route,
    RouterUpdate,
    SaidaGrafo,
)
from frigus_ai.infra.logging import Logging
from frigus_ai.infra.mongo import mongo
from frigus_ai.settings import settings

logger = Logging.get_logger(__name__)

_PING_TIMEOUT_S = 5

type GrafoFrigus = CompiledStateGraph[Estado, ContextoPrompt, EntradaGrafo, SaidaGrafo]


def decidir_apos_guardrail_entrada(estado: Estado) -> str:
    if estado.get("mensagem_bloqueada"):
        return Route.FIM
    # O roteador decide por texto e não sabe lidar com imagem: turno com foto pula
    # direto pra visão, sem passar pelo LLM de roteamento.
    if estado.get("tem_imagem"):
        return VISAO
    return ROTEADOR


NO_POR_DOMINIO: Mapping[RotaEspecialista, NodeLiteral] = {
    "estoque":    ESTOQUE,
    "compras":    COMPRAS,
    "receitas":   RECEITAS,
    "faq":        FAQ,
    "financeiro": FINANCEIRO,
    "assessor":   A2A_ASSESSOR,
}


def decidir_especialistas(estado: Estado) -> list[str] | str:
    """Os nós dos domínios escolhidos, que rodam em paralelo; nenhum = o roteador já respondeu."""

    nos = [NO_POR_DOMINIO[dominio] for dominio in estado.get("especialistas", [])]
    return nos or END


def decidir_apos_orquestrador(estado: Estado) -> str:
    """Sem nenhum especialista com dado (ex.: Assessor fora do ar) não há o que o Juiz conferir:
    ele só reprovaria o aviso de erro, e cada retry pagaria de novo o timeout de rede."""

    tem_dados = any(r["dados"] for r in estado["dados_especialistas"])
    return JUIZ if tem_dados else GUARDRAIL_SAIDA


def decidir_apos_juiz(estado: Estado) -> str:
    """Juiz reprovou e ainda pode pedir reescrita: o orquestrador reescreve com o feedback (repetir os
    especialistas regravaria estoque e lista de compras); senão segue pro guardrail de saída."""

    return ORQUESTRADOR if estado.get("feedback_juiz") else GUARDRAIL_SAIDA


def _construir_grafo() -> StateGraph:
    guardrail_entrada: AsyncNode[GuardrailEntradaUpdate]    = no_guardrail_entrada
    roteador:          AsyncNodeComContexto[RouterUpdate]       = no_roteador
    estoque:           AsyncNodeComContexto[EspecialistaUpdate] = no_estoque
    compras:           AsyncNodeComContexto[EspecialistaUpdate] = no_compras
    financeiro:        AsyncNodeComContexto[EspecialistaUpdate] = no_financeiro
    receitas:          AsyncNodeComContexto[EspecialistaUpdate] = no_receitas
    faq:               AsyncNodeComContexto[EspecialistaUpdate] = no_faq
    assessor:          AsyncNodeComContexto[EspecialistaUpdate] = no_assessor
    visao:             AsyncNodeComContexto[EspecialistaUpdate] = no_visao
    orquestrador:      AsyncNodeComContexto[OrquestradorUpdate] = no_orquestrador
    juiz:              AsyncNode[JuizUpdate]                    = no_juiz
    guardrail_saida:   AsyncNode[GuardrailSaidaUpdate]          = no_guardrail_saida

    grafo = StateGraph(
        Estado, context_schema=ContextoPrompt, input_schema=EntradaGrafo, output_schema=SaidaGrafo
    )

    grafo.add_node(GUARDRAIL_ENTRADA, guardrail_entrada)
    grafo.add_node(ROTEADOR,          roteador)
    grafo.add_node(ESTOQUE,           estoque)
    grafo.add_node(COMPRAS,           compras)
    grafo.add_node(RECEITAS,          receitas)
    grafo.add_node(FAQ,               faq)
    grafo.add_node(FINANCEIRO,        financeiro)
    grafo.add_node(A2A_ASSESSOR,      assessor)
    grafo.add_node(VISAO,             visao)
    grafo.add_node(ORQUESTRADOR,      orquestrador)
    grafo.add_node(JUIZ,              juiz)
    grafo.add_node(GUARDRAIL_SAIDA,   guardrail_saida)

    grafo.set_entry_point(GUARDRAIL_ENTRADA)

    grafo.add_conditional_edges(
        source   = GUARDRAIL_ENTRADA,
        path     = decidir_apos_guardrail_entrada,
        path_map = {
            Route.FIM: END,
            ROTEADOR:  ROTEADOR,
            VISAO:     VISAO,
        },
    )

    # Vários domínios -> vários nós na mesma etapa; o orquestrador roda uma vez, depois de todos.
    grafo.add_conditional_edges(
        source   = ROTEADOR,
        path     = decidir_especialistas,
        path_map = {**{no: no for no in NO_POR_DOMINIO.values()}, END: END},
    )

    for especialista in (*NO_POR_DOMINIO.values(), VISAO):
        grafo.add_edge(especialista, ORQUESTRADOR)

    grafo.add_conditional_edges(
        source   = ORQUESTRADOR,
        path     = decidir_apos_orquestrador,
        path_map = {JUIZ: JUIZ, GUARDRAIL_SAIDA: GUARDRAIL_SAIDA},
    )

    grafo.add_conditional_edges(
        source   = JUIZ,
        path     = decidir_apos_juiz,
        path_map = {ORQUESTRADOR: ORQUESTRADOR, GUARDRAIL_SAIDA: GUARDRAIL_SAIDA},
    )

    grafo.add_edge(GUARDRAIL_SAIDA, END)

    return grafo


async def _criar_checkpointer() -> BaseCheckpointSaver:
    """
    Faz `ping` porque o cliente do Mongo conecta de forma preguiçosa. `MemorySaver` só em `local`;
    em production o boot falha alto (cair em silêncio perderia os checkpoints a cada restart).
    """

    try:
        await asyncio.wait_for(asyncio.to_thread(mongo.client.admin.command, "ping"), _PING_TIMEOUT_S)
        return MongoDBSaver(
            mongo.client,
            db_name=mongo.banco.name,
            checkpoint_collection_name="graph_checkpoints",
            writes_collection_name="graph_checkpoint_writes",
        )
    except Exception as e:
        if settings.environment != "local":
            raise
        logger.warning("Mongo indisponível (%s) — checkpoints em memória (somem no restart).", e)
        return MemorySaver()


class FluxoAgentes:
    """Compila o grafo e prepara o checkpointer uma vez por processo; o `lock` evita duplicar no 1º uso concorrente."""

    def __init__(self) -> None:
        self._compilado: GrafoFrigus | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> GrafoFrigus:
        if self._compilado is not None:
            return self._compilado

        async with self._lock:
            if self._compilado is None:
                checkpointer = await _criar_checkpointer()
                self._compilado = _construir_grafo().compile(checkpointer=checkpointer)

        return self._compilado

    async def aclose(self) -> None:
        """Invalida o grafo compilado. Chamado pelo lifespan no shutdown."""

        async with self._lock:
            self._compilado = None


fluxo_agentes = FluxoAgentes()


__all__ = ["FluxoAgentes", "GrafoFrigus", "fluxo_agentes"]
