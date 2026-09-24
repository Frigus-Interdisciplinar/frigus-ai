import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import cast, get_args

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from frigus_ai.graph.agents import conversas_anteriores
from frigus_ai.graph.builder import fluxo_agentes
from frigus_ai.graph.names import NodeLiteral
from frigus_ai.graph.state import EntradaGrafo, RouteLiteral
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.logging import Logging
from frigus_ai.observability.metrics import GRAPH_DURATION, GRAPH_RUNS
from frigus_ai.observability.metrics_callback import PrometheusCallbackHandler
from frigus_ai.repositories import chat_embeddings_repository
from frigus_ai.schemas.execution import (
    AnswerReady,
    ExecutionEvent,
    NodeFinished,
    NodeStarted,
    RouteSelected,
    RunFailed,
    RunFinished,
    RunStarted,
)

logger = Logging.get_logger(__name__)

# Nomes registrados via StateGraph.add_node() — event["name"] do astream_events bate com essa
# string exata pro evento de início/fim do node em si (metadata["langgraph_node"] é herdado por
# todo runnable filho, event["name"] não é: por isso filtramos por name, não por metadata).
_NOMES_DE_NODE = frozenset(get_args(NodeLiteral))


def _extrair_resposta(estado: Mapping[str, object]) -> str | None:
    """
    Última mensagem de IA do estado — seja o estado final consolidado do `ainvoke`,
    seja o delta de um nó vindo do `astream`.
    """

    mensagens = estado.get("messages") or []
    assert isinstance(mensagens, Sequence)

    for msg in list(mensagens)[::-1]:
        if isinstance(msg, AIMessage):
            return msg.text
    return None


def _estado_inicial(
    conteudo: str, stock_id: int | None, imagem_b64: str | None = None
) -> EntradaGrafo:
    """
    Só os campos de `EntradaGrafo`: o resto do `Estado` é interno do grafo. `agentes_chamados`
    parte vazio pelo reducer e `tentativas_juiz` é zerado pelo roteador a cada turno.
    """

    mensagens: list[AnyMessage] = [HumanMessage(content=conteudo)]

    entrada = EntradaGrafo(
        messages=mensagens,
        stock_id=stock_id,
    )
    if imagem_b64:
        entrada["imagem_b64"] = imagem_b64

    return entrada


async def _carregar_conversas_anteriores(
    conteudo: str, session_id: str, user_id: int, imagem_b64: str | None
) -> None:
    """
    Memória de longo prazo é opcional: Qdrant/embedding fora do ar não pode derrubar o
    turno. Sempre seta (vazio inclusive) — o ContextVar não é resetado no fim, então é
    isso que impede o valor de um turno vazar pro próximo na mesma task (MCP/TUI).
    """

    resumos: list[str] = []
    if not imagem_b64:  # foto não tem pergunta em texto pra buscar
        try:
            resumos = await chat_embeddings_repository.buscar_resumos_relevantes(
                user_id, conteudo, session_id
            )
        except Exception as e:
            logger.warning(f"Busca de conversas anteriores falhou, seguindo sem: {e}")

    conversas_anteriores.set(tuple(resumos))


def _config(session_id: str, user_id: int) -> RunnableConfig:
    return {
        "configurable": {"thread_id": session_id},
        "tags": ["chat"],
        "metadata": {"user_id": user_id, "session_id": session_id},
        # Uma instância por turno — os mapas internos de run_id não podem vazar
        # entre chamadas/usuários concorrentes (ver metrics_callback.py).
        "callbacks": [PrometheusCallbackHandler()],
    }


async def executar(
    conteudo: str,
    session_id: str,
    user_id: int,
    stock_id: int | None,
    imagem_b64: str | None = None,
) -> str | None:
    inicio = time.perf_counter()
    outcome = "error"

    await _carregar_conversas_anteriores(conteudo, session_id, user_id, imagem_b64)

    try:
        # stock_id/user_id ficam disponíveis via contextvars para as tools de
        # Postgres (tools/postgres/context.py) durante toda a invocação do grafo.
        with session_context(user_id=user_id, stock_id=stock_id):
            grafo = await fluxo_agentes.get()
            estado_final = await grafo.ainvoke(
                _estado_inicial(conteudo, stock_id, imagem_b64),
                config=_config(session_id, user_id),
            )

        outcome = "success"
        return _extrair_resposta(estado_final)
    finally:
        GRAPH_RUNS.labels(outcome=outcome).inc()
        GRAPH_DURATION.labels(outcome=outcome).observe(time.perf_counter() - inicio)


async def executar_stream(
    conteudo: str,
    session_id: str,
    user_id: int,
    stock_id: int | None,
    imagem_b64: str | None = None,
) -> AsyncIterator[ExecutionEvent]:
    """
    Mesma execução de `executar()`, mas emite a timeline de nodes em tempo real via
    `astream_events` — consumida pelo painel de grafo do frontend.

    Sem streaming de token da resposta final: quem responde (`guardrail_saida`, ou o
    roteador/guardrail de entrada respondendo direto em `Route.FIM`) só está seguro
    de mostrar depois de processar o texto inteiro, não em fragmentos — daí
    `AnswerReady` chegar pronta, não como uma sequência de deltas.
    """

    yield RunStarted()

    await _carregar_conversas_anteriores(conteudo, session_id, user_id, imagem_b64)

    inicio = time.perf_counter()
    outcome = "error"
    resposta_final: str | None = None

    try:
        with session_context(user_id=user_id, stock_id=stock_id):
            grafo = await fluxo_agentes.get()

            async for event in grafo.astream_events(
                _estado_inicial(conteudo, stock_id, imagem_b64),
                config=_config(session_id, user_id),
                version="v2",
            ):
                nome = event.get("name")
                if nome not in _NOMES_DE_NODE:
                    continue

                tipo = event.get("event")

                if tipo == "on_chain_start":
                    yield NodeStarted(node=cast(NodeLiteral, nome))
                    continue

                if tipo != "on_chain_end":
                    continue

                output = event.get("data", {}).get("output")

                if isinstance(output, dict):
                    if (rota := output.get("rota")) is not None:
                        yield RouteSelected(route=cast(RouteLiteral, rota))

                    resposta_final = _extrair_resposta(output) or resposta_final

                yield NodeFinished(node=cast(NodeLiteral, nome))

        outcome = "success"

        if resposta_final is not None:
            yield AnswerReady(content=resposta_final)

        yield RunFinished()
    except Exception:
        logger.exception(f"Falha durante streaming da execução do agente | session_id={session_id}")
        yield RunFailed(message="Não foi possível processar a mensagem.")
    finally:
        GRAPH_RUNS.labels(outcome=outcome).inc()
        GRAPH_DURATION.labels(outcome=outcome).observe(time.perf_counter() - inicio)
