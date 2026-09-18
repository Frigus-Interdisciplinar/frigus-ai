"""Configuração de segurança do fastapi-guard e middleware de métricas HTTP."""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import Response
from guard import SecurityConfig, SecurityMiddleware

from frigus_ai.evals.metrics import ACTIVE_REQUESTS, HTTP_DURATION, HTTP_REQUESTS
from frigus_ai.settings import settings

type CallNext = Callable[[Request], Awaitable[Response]]


def security_config() -> SecurityConfig:
    return SecurityConfig(
        # settings.REDIS_URL já é `str` aqui (assessor_ai usa SecretStr, este projeto não).
        redis_url=settings.REDIS_URL,
        enable_rate_limiting=settings.API_KEY_AUTH_ENABLED,
        enable_cors=True,
        cors_allow_origins=["*"],
        cors_allow_methods=["GET", "POST"],
        cors_allow_headers=["*"],
        cors_allow_credentials=False,
        cors_expose_headers=["X-Custom-Header"],
    )


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)

    return path if isinstance(path, str) else "unmatched"


async def observar_http(request: Request, call_next: CallNext) -> Response:
    # A coleta do próprio Prometheus não deve virar métrica de si mesma.
    if request.url.path.startswith("/metrics"):
        return await call_next(request)

    inicio = time.perf_counter()
    status_code = 500
    ACTIVE_REQUESTS.inc()

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duracao = time.perf_counter() - inicio
        rota = _route_template(request)
        status_class = f"{status_code // 100}xx"

        ACTIVE_REQUESTS.dec()
        HTTP_REQUESTS.labels(method=request.method, route=rota, status_class=status_class).inc()
        HTTP_DURATION.labels(method=request.method, route=rota).observe(duracao)


def adicionar_middleware(app: FastAPI) -> None:
    app.middleware("http")(observar_http)
    if settings.API_KEY_AUTH_ENABLED:
        app.add_middleware(SecurityMiddleware, config=security_config())


__all__ = ["adicionar_middleware", "observar_http", "security_config"]
