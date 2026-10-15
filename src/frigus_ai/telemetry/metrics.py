"""
Métricas Prometheus (agregados: p95, falhas, tokens); o trace de cada turno fica no LangSmith.
Exposto em `/metrics`: em produção só pra Prometheus/rede interna.
"""

import functools
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import ParamSpec, TypeVar

from prometheus_client import Counter, Gauge, Histogram

P = ParamSpec("P")
R = TypeVar("R")

HTTP_REQUESTS = Counter(
    "frigus_http_requests_total",
    "Total de requests HTTP.",
    labelnames=("method", "route", "status_class"),
)

HTTP_UNMATCHED = Counter(
    "frigus_http_unmatched_total",
    "Requests que não casaram com nenhuma rota (404 de path inexistente).",
    labelnames=("method",),
)

HTTP_DURATION = Histogram(
    "frigus_http_request_duration_seconds",
    "Duração dos requests HTTP.",
    labelnames=("method", "route"),
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

ACTIVE_REQUESTS = Gauge(
    "frigus_http_active_requests",
    "Requests HTTP atualmente em execução.",
)


# SLO do turno de chat, exportado como `frigus_slo_target` pra Grafana, alertas e relatório lerem
# do mesmo lugar. SLIs: p95 de `frigus_graph_duration_seconds` e erro = outcome="error" / turnos.
# Bloqueio do guardrail (outcome="blocked") não é erro. Não há SLA (sem contrato).
SLO_LATENCIA_P95_S = 8.0
SLO_TAXA_ERRO = 0.05

SLO_TARGET = Gauge(
    "frigus_slo_target",
    "Limites do SLO do turno de chat (latency_p95_seconds, error_ratio).",
    labelnames=("sli",),
)
SLO_TARGET.labels(sli="latency_p95_seconds").set(SLO_LATENCIA_P95_S)
SLO_TARGET.labels(sli="error_ratio").set(SLO_TAXA_ERRO)

GRAPH_RUNS = Counter(
    "frigus_graph_runs_total",
    "Turnos completos do LangGraph por outcome (success, blocked, error).",
    labelnames=("outcome",),
)

GRAPH_IN_PROGRESS = Gauge(
    "frigus_graph_in_progress",
    "Turnos do grafo em execução agora (saturação — proxy, o modelo é API de terceiro).",
)

GRAPH_DURATION = Histogram(
    "frigus_graph_duration_seconds",
    "Duração completa de uma execução do LangGraph.",
    labelnames=("outcome",),
    buckets=(0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120),
)


NODE_RUNS = Counter(
    "frigus_node_runs_total",
    "Execuções de nodes do LangGraph.",
    labelnames=("node", "outcome"),
)

NODE_DURATION = Histogram(
    "frigus_node_duration_seconds",
    "Duração dos nodes do LangGraph.",
    labelnames=("node", "outcome"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)


TOOL_RUNS = Counter(
    "frigus_tool_runs_total",
    "Execuções de tools observadas pelo LangChain.",
    labelnames=("tool", "termination"),
)

TOOL_DURATION = Histogram(
    "frigus_tool_duration_seconds",
    "Duração de tools.",
    labelnames=("tool", "termination"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


LLM_RUNS = Counter(
    "frigus_llm_runs_total",
    "Chamadas de modelos.",
    labelnames=("provider", "model", "node", "outcome"),
)

LLM_DURATION = Histogram(
    "frigus_llm_duration_seconds",
    "Duração das chamadas de modelos.",
    labelnames=("provider", "model", "node", "outcome"),
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60),
)

LLM_TOKENS = Counter(
    "frigus_llm_tokens_total",
    "Tokens consumidos pelos modelos.",
    labelnames=("provider", "model", "direction"),
)

LLM_COST = Counter(
    "frigus_llm_cost_usd_total",
    "Custo estimado em USD (tokens × tabela fixa de preços, sem desconto de cache — não é a fatura).",
    labelnames=("provider", "model"),
)

LLM_FALLBACKS = Counter(
    "frigus_llm_fallbacks_total",
    "Chamadas de especialista que não saíram do modelo principal (Gemini caiu, fallback assumiu).",
    labelnames=("node", "model"),
)


ROUTER_DECISIONS = Counter(
    "frigus_router_decisions_total",
    "Rotas escolhidas pelo router.",
    labelnames=("route",),
)

GUARDRAIL_DECISIONS = Counter(
    "frigus_guardrail_decisions_total",
    "Decisões do guardrail de entrada.",
    labelnames=("decision",),
)

RATE_LIMIT_REJECTIONS = Counter(
    "frigus_rate_limit_rejections_total",
    "Requisições rejeitadas por rate limiting.",
    labelnames=("scope",),
)

GUARD_BLOCKS = Counter(
    "frigus_guard_blocks_total",
    "Requests barrados pelo fastapi-guard, por check (rate_limit, ip_security, ...).",
    labelnames=("check",),
)


MEMORY_UPDATES = Counter(
    "frigus_memory_updates_total",
    "Etapas da atualização de memória em segundo plano (fatos, resumo, embedding no Qdrant).",
    labelnames=("etapa", "outcome"),
)

MEMORY_UPDATE_DURATION = Histogram(
    "frigus_memory_update_duration_seconds",
    "Duração de cada etapa da atualização de memória.",
    labelnames=("etapa", "outcome"),
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60),
)

MEMORY_PENDING = Gauge(
    "frigus_memory_pending",
    "Chats com resumo ou embedding atrasado, visto no último ciclo do reconciliador.",
)

MEMORY_RETRIEVAL_HITS = Histogram(
    "frigus_memory_retrieval_hits",
    "Resumos de conversas anteriores recuperados do Qdrant por turno.",
    buckets=(0, 1, 2, 3),
)

BACKGROUND_TASKS = Gauge(
    "frigus_background_tasks",
    "Tarefas de segundo plano (memória, persistência) em execução.",
)

CHAT_PERSIST_FAILURES = Counter(
    "frigus_chat_persist_failures_total",
    "Falhas ao gravar o turno (pergunta + resposta) no Mongo.",
    labelnames=("via",),
)

SSE_DISCONNECTS = Counter(
    "frigus_sse_disconnects_total",
    "Streams SSE encerrados pelo cliente antes do fim da execução.",
)

EXTERNAL_CALLS = Counter(
    "frigus_external_calls_total",
    "Chamadas a serviços externos.",
    labelnames=("target", "outcome"),
)

EXTERNAL_DURATION = Histogram(
    "frigus_external_call_duration_seconds",
    "Duração das chamadas a serviços externos.",
    labelnames=("target", "outcome"),
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

DEPENDENCY_UP = Gauge(
    "frigus_dependency_up",
    "1 se a dependência respondeu no último /health/ready, 0 se não.",
    labelnames=("dep",),
)


@contextmanager
def _medir(contador: Counter, histograma: Histogram, **labels: str) -> Iterator[None]:
    inicio = time.perf_counter()
    outcome = "error"

    try:
        yield
        outcome = "success"
    finally:
        contador.labels(**labels, outcome=outcome).inc()
        histograma.labels(**labels, outcome=outcome).observe(time.perf_counter() - inicio)


def medir_externo(target: str) -> AbstractContextManager[None]:
    """`with medir_externo("qdrant"):` — conta e cronometra; exceção vira `outcome="error"`."""

    return _medir(EXTERNAL_CALLS, EXTERNAL_DURATION, target=target)


def medir_memoria(etapa: str) -> AbstractContextManager[None]:
    return _medir(MEMORY_UPDATES, MEMORY_UPDATE_DURATION, etapa=etapa)


def medir_node(nome: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator pros nodes do grafo — preserva a assinatura original via ParamSpec/TypeVar."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            inicio = time.perf_counter()
            outcome = "error"

            try:
                resultado = await func(*args, **kwargs)
                outcome = "success"
                return resultado
            finally:
                duracao = time.perf_counter() - inicio
                NODE_RUNS.labels(node=nome, outcome=outcome).inc()
                NODE_DURATION.labels(node=nome, outcome=outcome).observe(duracao)

        return wrapper

    return decorator


__all__ = [
    "ACTIVE_REQUESTS",
    "BACKGROUND_TASKS",
    "CHAT_PERSIST_FAILURES",
    "DEPENDENCY_UP",
    "EXTERNAL_CALLS",
    "EXTERNAL_DURATION",
    "GRAPH_DURATION",
    "GRAPH_IN_PROGRESS",
    "GRAPH_RUNS",
    "GUARDRAIL_DECISIONS",
    "GUARD_BLOCKS",
    "HTTP_DURATION",
    "HTTP_REQUESTS",
    "HTTP_UNMATCHED",
    "LLM_COST",
    "LLM_DURATION",
    "LLM_FALLBACKS",
    "LLM_RUNS",
    "LLM_TOKENS",
    "MEMORY_PENDING",
    "MEMORY_RETRIEVAL_HITS",
    "MEMORY_UPDATES",
    "MEMORY_UPDATE_DURATION",
    "NODE_DURATION",
    "NODE_RUNS",
    "RATE_LIMIT_REJECTIONS",
    "ROUTER_DECISIONS",
    "SLO_LATENCIA_P95_S",
    "SLO_TARGET",
    "SLO_TAXA_ERRO",
    "SSE_DISCONNECTS",
    "TOOL_DURATION",
    "TOOL_RUNS",
    "medir_externo",
    "medir_memoria",
    "medir_node",
]
