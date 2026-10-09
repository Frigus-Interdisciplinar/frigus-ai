import asyncio
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, cast, get_args

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from frigus_ai.graph.builder import fluxo_agentes
from frigus_ai.graph.names import NodeLiteral
from frigus_ai.graph.state import ContextoPrompt, EntradaGrafo, RouteLiteral
from frigus_ai.infra.logging import Logging
from frigus_ai.infra.postgres.context import session_context
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
from frigus_ai.services.user_service import user_service
from frigus_ai.telemetry.metrics import GRAPH_DURATION, GRAPH_IN_PROGRESS, GRAPH_RUNS
from frigus_ai.telemetry.metrics_callback import PrometheusCallbackHandler

logger = Logging.get_logger(__name__)

# O nome do evento do `astream_events` bate com o nome registrado no `add_node`; filtramos por
# `name` porque `metadata["langgraph_node"]` é herdado por todo runnable filho.
_NOMES_DE_NODE = frozenset(get_args(NodeLiteral))


def _extrair_resposta(estado: Mapping[str, object]) -> str | None:
    """Última mensagem de IA do estado (final do `ainvoke` ou delta de um node)."""

    mensagens = estado.get("messages") or []
    if not isinstance(mensagens, Sequence):
        raise TypeError(f"esperava Sequence, veio {type(mensagens).__name__}")

    for msg in list(mensagens)[::-1]:
        if isinstance(msg, AIMessage):
            return msg.text
    return None


def _estado_inicial(
    conteudo: str,
    stock_id: int | None,
    imagem_b64: str | None = None,
) -> EntradaGrafo:
    """Só os campos de `EntradaGrafo`; o resto do `Estado` é interno do grafo."""

    mensagens: list[AnyMessage] = [HumanMessage(content=conteudo)]

    entrada = EntradaGrafo(
        messages=mensagens,
        stock_id=stock_id,
    )
    if imagem_b64:
        entrada["imagem_b64"] = imagem_b64

    return entrada


async def _carregar_contexto(
    conteudo: str, session_id: str, user_id: str, imagem_b64: str | None
) -> ContextoPrompt:
    """Fatos e conversas anteriores, opcionais: banco fora do ar não derruba o turno. Vai por
    `context=`, fora do checkpoint — falha aqui deixa o turno sem perfil, nunca com o antigo."""

    fatos = None
    try:
        fatos = await user_service.buscar_fatos(user_id)
    except Exception as e:
        logger.warning("Busca de fatos falhou, seguindo sem: %s", e)

    resumos: list[str] = []
    if not imagem_b64:  # foto não tem pergunta em texto pra buscar
        try:
            resumos = await chat_embeddings_repository.buscar_resumos_relevantes(
                user_id, conteudo, session_id
            )
        except Exception as e:
            logger.warning("Busca de conversas anteriores falhou, seguindo sem: %s", e)

    return ContextoPrompt(fatos=fatos, conversas=tuple(resumos))


def _outcome(estado: Mapping[str, Any]) -> str:
    """Bloqueio do guardrail de entrada é o sistema funcionando: conta à parte, não como
    erro do SLO (nem como resolução no `sre_report`)."""

    return "blocked" if estado.get("mensagem_bloqueada") else "success"


def _config(session_id: str, user_id: str) -> RunnableConfig:
    return {
        "configurable": {"thread_id": session_id},
        "tags": ["chat"],
        "metadata": {"user_id": user_id, "session_id": session_id},
        # Uma instância por turno — os mapas internos de run_id não podem vazar
        # entre chamadas/usuários concorrentes (ver metrics_callback.py).
        "callbacks": [PrometheusCallbackHandler()],
    }


async def descartar_thread(thread_id: str) -> None:
    """
    Apaga todos os checkpoints de uma thread descartável (foto): cada passo do grafo grava o
    `imagem_b64` inteiro. Falha só loga, a resposta já foi dada.
    """

    try:
        grafo = await fluxo_agentes.get()
        if grafo.checkpointer:
            await asyncio.to_thread(grafo.checkpointer.delete_thread, thread_id)
    except Exception as e:
        logger.warning("Não consegui apagar a thread %s: %s", thread_id, e)


async def executar(
    conteudo: str,
    session_id: str,
    user_id: str,
    stock_id: int | None,
    imagem_b64: str | None = None,
) -> str | None:
    inicio = time.perf_counter()
    outcome = "error"

    contexto = await _carregar_contexto(conteudo, session_id, user_id, imagem_b64)

    GRAPH_IN_PROGRESS.inc()
    try:
        # stock_id/user_id ficam disponíveis via contextvars para as tools de
        # Postgres (tools/postgres/context.py) durante toda a invocação do grafo.
        with session_context(user_id=user_id, stock_id=stock_id):
            grafo = await fluxo_agentes.get()
            estado_final = await grafo.ainvoke(
                _estado_inicial(conteudo, stock_id, imagem_b64),
                context=contexto,
                config=_config(session_id, user_id),
            )

        outcome = _outcome(estado_final)
        return _extrair_resposta(estado_final)
    finally:
        GRAPH_IN_PROGRESS.dec()
        GRAPH_RUNS.labels(outcome=outcome).inc()
        GRAPH_DURATION.labels(outcome=outcome).observe(time.perf_counter() - inicio)


async def executar_stream(
    conteudo: str,
    session_id: str,
    user_id: str,
    stock_id: int | None,
    imagem_b64: str | None = None,
) -> AsyncIterator[ExecutionEvent]:
    """
    Como `executar()`, emitindo a timeline de nodes via `astream_events` (painel de grafo do
    front). Sem streaming de token: a resposta só é segura de mostrar depois de pronta
    (guardrail de saída), então `AnswerReady` chega inteira.
    """

    yield RunStarted()

    contexto = await _carregar_contexto(conteudo, session_id, user_id, imagem_b64)

    inicio = time.perf_counter()
    outcome = "error"
    bloqueado = False
    resposta_final: str | None = None

    GRAPH_IN_PROGRESS.inc()
    try:
        with session_context(user_id=user_id, stock_id=stock_id):
            grafo = await fluxo_agentes.get()

            async for event in grafo.astream_events(
                _estado_inicial(conteudo, stock_id, imagem_b64),
                context=contexto,
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
                    bloqueado = bloqueado or _outcome(output) == "blocked"
                    if (rota := output.get("rota")) is not None:
                        yield RouteSelected(route=cast(RouteLiteral, rota))

                    resposta_final = _extrair_resposta(output) or resposta_final

                yield NodeFinished(node=cast(NodeLiteral, nome))

        outcome = "blocked" if bloqueado else "success"

        if resposta_final is not None:
            yield AnswerReady(content=resposta_final)

        yield RunFinished()
    except Exception:
        logger.exception("Falha durante streaming da execução do agente | session_id=%s", session_id)
        yield RunFailed(message="Não foi possível processar a mensagem.")
    finally:
        GRAPH_IN_PROGRESS.dec()
        GRAPH_RUNS.labels(outcome=outcome).inc()
        GRAPH_DURATION.labels(outcome=outcome).observe(time.perf_counter() - inicio)
