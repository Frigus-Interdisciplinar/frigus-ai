import asyncio
from typing import get_args

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from frigus_ai.graph.guardrail.entrada import no_guardrail_entrada
from frigus_ai.graph.guardrail.saida import no_guardrail_saida
from frigus_ai.graph.names import (
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
)
from frigus_ai.graph.nodes import (
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
    EntradaGrafo,
    EspecialistaUpdate,
    Estado,
    FaqUpdate,
    GuardrailEntradaUpdate,
    GuardrailSaidaUpdate,
    JuizUpdate,
    OrquestradorUpdate,
    RotaEspecialista,
    Route,
    RouterUpdate,
    SaidaGrafo,
)
from frigus_ai.infra.mongo.connection import mongo

type GrafoFrigus = CompiledStateGraph[Estado, None, EntradaGrafo, SaidaGrafo]


def decidir_apos_guardrail_entrada(estado: Estado) -> str:
    if estado.get("mensagem_bloqueada"):
        return Route.FIM
    # O roteador decide por texto e não sabe lidar com imagem: turno com foto pula
    # direto pra visão, sem passar pelo LLM de roteamento.
    if estado.get("imagem_b64"):
        return VISAO
    return ROTEADOR


_ESPECIALISTAS = frozenset(get_args(RotaEspecialista))


def decidir_especialista(estado: Estado) -> str:
    rota = estado.get("rota", Route.FIM)
    if rota not in _ESPECIALISTAS:
        return Route.FIM
    return rota


def decidir_apos_juiz(estado: Estado) -> str:
    """
    Se o Juiz reprovou e ainda há tentativas disponíveis (feedback_juiz preenchido
    por no_juiz), volta para o MESMO especialista que originou a rota. Caso
    contrário (aprovado, ou tentativas esgotadas), segue para o Guardrail de Saída.
    """

    if estado.get("feedback_juiz"):
        return estado.get("rota", GUARDRAIL_SAIDA)
    return GUARDRAIL_SAIDA


def _construir_grafo() -> StateGraph:
    guardrail_entrada: AsyncNode[GuardrailEntradaUpdate] = no_guardrail_entrada
    roteador:          AsyncNode[RouterUpdate]           = no_roteador
    estoque:           AsyncNode[EspecialistaUpdate]     = no_estoque
    compras:           AsyncNode[EspecialistaUpdate]     = no_compras
    financeiro:        AsyncNode[EspecialistaUpdate]     = no_financeiro
    receitas:          AsyncNode[FaqUpdate]              = no_receitas
    faq:               AsyncNode[FaqUpdate]              = no_faq
    visao:             AsyncNode[EspecialistaUpdate]     = no_visao
    orquestrador:      AsyncNode[OrquestradorUpdate]     = no_orquestrador
    juiz:              AsyncNode[JuizUpdate]             = no_juiz
    guardrail_saida:   AsyncNode[GuardrailSaidaUpdate]   = no_guardrail_saida

    grafo = StateGraph(Estado, input_schema=EntradaGrafo, output_schema=SaidaGrafo)

    grafo.add_node(GUARDRAIL_ENTRADA, guardrail_entrada)
    grafo.add_node(ROTEADOR,          roteador)
    grafo.add_node(ESTOQUE,           estoque)
    grafo.add_node(COMPRAS,           compras)
    grafo.add_node(RECEITAS,          receitas)
    grafo.add_node(FAQ,               faq)
    grafo.add_node(FINANCEIRO,        financeiro)
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

    grafo.add_conditional_edges(
        source   = ROTEADOR,
        path     = decidir_especialista,
        path_map = {
            Route.ESTOQUE:    ESTOQUE,
            Route.COMPRAS:    COMPRAS,
            Route.RECEITAS:   RECEITAS,
            Route.FAQ:        FAQ,
            Route.FINANCEIRO: FINANCEIRO,
            Route.FIM:        END,
        },
    )

    # Estoque/Compras/Financeiro/Visão produzem JSON estruturado -> Orquestrador formata em linguagem natural
    grafo.add_edge(ESTOQUE,      ORQUESTRADOR)
    grafo.add_edge(COMPRAS,      ORQUESTRADOR)
    grafo.add_edge(FINANCEIRO,   ORQUESTRADOR)
    grafo.add_edge(VISAO,        ORQUESTRADOR)
    grafo.add_edge(ORQUESTRADOR, JUIZ)

    # Receitas/FAQ já respondem em linguagem natural -> vão direto para o Juiz
    grafo.add_edge(RECEITAS, JUIZ)
    grafo.add_edge(FAQ,      JUIZ)

    # Juiz: reprovado + tentativas disponíveis -> volta pro especialista de origem; caso contrário -> Guardrail de Saída
    grafo.add_conditional_edges(
        source   = JUIZ,
        path     = decidir_apos_juiz,
        path_map = {
            Route.ESTOQUE:    ESTOQUE,
            Route.COMPRAS:    COMPRAS,
            Route.RECEITAS:   RECEITAS,
            Route.FAQ:        FAQ,
            Route.FINANCEIRO: FINANCEIRO,
            GUARDRAIL_SAIDA:  GUARDRAIL_SAIDA,
        },
    )

    grafo.add_edge(GUARDRAIL_SAIDA, END)

    return grafo


class FluxoAgentes:
    """
    Compila o grafo + prepara o checkpointer uma vez por processo e reusa nas requests.

    O `lock` cobre os pontos de entrada que chamam `get()` concorrentemente no primeiro uso
    (lifespan, e qualquer chamada direta antes dele) — sem ele, duas chamadas concorrentes
    abririam dois checkpointers MongoDB e compilariam o grafo duas vezes.
    """

    def __init__(self) -> None:
        self._compilado: GrafoFrigus | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> GrafoFrigus:
        if self._compilado is not None:
            return self._compilado

        async with self._lock:
            if self._compilado is None:
                checkpointer = MongoDBSaver(
                    mongo.client,
                    db_name=mongo.banco.name,
                    checkpoint_collection_name="graph_checkpoints",
                    writes_collection_name="graph_checkpoint_writes",
                )
                self._compilado = _construir_grafo().compile(checkpointer=checkpointer)

        return self._compilado

    async def aclose(self) -> None:
        """Invalida o grafo compilado. Chamado pelo lifespan no shutdown."""

        async with self._lock:
            self._compilado = None


fluxo_agentes = FluxoAgentes()


__all__ = ["FluxoAgentes", "GrafoFrigus", "fluxo_agentes"]
