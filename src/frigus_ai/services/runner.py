import time
from collections.abc import AsyncIterator, Mapping, Sequence

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from frigus_ai.evals.metrics import GRAPH_DURATION, GRAPH_RUNS
from frigus_ai.evals.metrics_callback import PrometheusCallbackHandler
from frigus_ai.graph.builder import fluxo_agentes
from frigus_ai.graph.state import EntradaGrafo
from frigus_ai.infra.postgres.context import session_context


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


def _estado_inicial(conteudo: str, stock_id: int | None, perfil_usuario: str) -> EntradaGrafo:
    """
    Só os campos de `EntradaGrafo`: o resto do `Estado` é interno do grafo. `agentes_chamados`
    parte vazio pelo reducer e `tentativas_juiz` é zerado pelo roteador a cada turno.
    """

    mensagens: list[AnyMessage] = [HumanMessage(content=conteudo)]

    return EntradaGrafo(
        messages=mensagens,
        perfil_usuario=perfil_usuario,
        stock_id=stock_id,
    )


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
    perfil_usuario: str,
) -> str | None:
    inicio = time.perf_counter()
    outcome = "error"

    try:
        # stock_id/user_id ficam disponíveis via contextvars para as tools de
        # Postgres (tools/postgres/context.py) durante toda a invocação do grafo.
        with session_context(user_id=user_id, stock_id=stock_id):
            grafo = await fluxo_agentes.get()
            estado_final = await grafo.ainvoke(
                _estado_inicial(conteudo, stock_id, perfil_usuario),
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
    perfil_usuario: str,
) -> AsyncIterator[tuple[str, str]]:
    """
    Emite `("no", nome_do_no)` a cada nó concluído e `("resposta", texto)` no fim.

    É progresso por nó, não token a token: quem produz o texto final é o
    `guardrail_saida`, que reescreve a resposta inteira depois que o LLM termina
    (`agents/nodes/guardrail/saida.py`) — não há token final pra streamar antes disso.
    """

    resposta = None
    inicio = time.perf_counter()
    outcome = "error"

    try:
        with session_context(user_id=user_id, stock_id=stock_id):
            grafo = await fluxo_agentes.get()
            async for update in grafo.astream(
                _estado_inicial(conteudo, stock_id, perfil_usuario),
                config=_config(session_id, user_id),
                stream_mode="updates",
            ):
                for no, delta in update.items():
                    yield "no", no
                    resposta = _extrair_resposta(delta or {}) or resposta

        outcome = "success"
        yield "resposta", resposta or "Sem resposta."
    finally:
        GRAPH_RUNS.labels(outcome=outcome).inc()
        GRAPH_DURATION.labels(outcome=outcome).observe(time.perf_counter() - inicio)
