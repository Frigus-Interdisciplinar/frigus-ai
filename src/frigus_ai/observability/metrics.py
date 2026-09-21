"""
Métricas Prometheus. LangSmith continua responsável pela execução individual (trace por turno,
prompt/resposta completos) — aqui é só o agregado: p95, contagem de falhas, tokens no período.

Exposto em `/metrics` por `api/app.py`. Não deixar esse endpoint público num deploy real — só
Prometheus/rede interna.
"""

import functools
import time
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from prometheus_client import Counter, Gauge, Histogram

P = ParamSpec("P")
R = TypeVar("R")

HTTP_REQUESTS = Counter(
    "frigus_http_requests_total",
    "Total de requests HTTP.",
    labelnames=("method", "route", "status_class"),
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


GRAPH_RUNS = Counter(
    "frigus_graph_runs_total",
    "Execuções completas do LangGraph.",
    labelnames=("outcome",),
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
    "GRAPH_DURATION",
    "GRAPH_RUNS",
    "GUARDRAIL_DECISIONS",
    "HTTP_DURATION",
    "HTTP_REQUESTS",
    "LLM_DURATION",
    "LLM_RUNS",
    "LLM_TOKENS",
    "NODE_DURATION",
    "NODE_RUNS",
    "RATE_LIMIT_REJECTIONS",
    "ROUTER_DECISIONS",
    "TOOL_DURATION",
    "TOOL_RUNS",
    "medir_node",
]
