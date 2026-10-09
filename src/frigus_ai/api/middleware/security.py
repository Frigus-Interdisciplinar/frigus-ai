"""Configuração do fastapi-guard (rate limit, CORS) e o `guard` que decora as rotas."""

from typing import Any

from guard import SecurityConfig, SecurityDecorator

from frigus_ai.settings import settings
from frigus_ai.telemetry.metrics import GUARD_BLOCKS, RATE_LIMIT_REJECTIONS

# Sem isso vale o default do guard (10 req/60s por IP em toda rota): SSE, polling e scrape davam 429.
# Rotas sensíveis têm limite próprio via `@guard.rate_limit` (precisa de `app.state.guard_decorator`).
_LIMITE_GLOBAL_POR_MINUTO = 120


def _contar_bloqueio(_request: Any, payload: dict[str, Any]) -> None:
    check = str(payload.get("check_name") or "unknown")
    GUARD_BLOCKS.labels(check=check).inc()
    if check == "rate_limit":
        RATE_LIMIT_REJECTIONS.labels(scope="http").inc()


def security_config() -> SecurityConfig:
    return SecurityConfig(
        redis_url=settings.database.redis_url,
        enable_rate_limiting=settings.api.key_auth_enabled,
        rate_limit=_LIMITE_GLOBAL_POR_MINUTO,
        rate_limit_window=60,
        # Probes e scrape não passam pelo guard: /metrics tem token próprio, /health não
        # pode virar 429 pro orquestrador derrubar o processo.
        exclude_paths=["/docs", "/redoc", "/openapi.json", "/favicon.ico", "/health", "/metrics"],
        on_block=_contar_bloqueio,
        redis_socket_connect_timeout=10.0,
        redis_socket_timeout=10.0,
        redis_retries=3,
        # Redis fora do ar: em local o rate limit é ignorado; em production a requisição é barrada.
        redis_fail_open=settings.environment == "local",
        enable_cors=True,
        cors_allow_origins=settings.api.cors_origins,
        cors_allow_methods=["GET", "POST", "PUT", "DELETE"],
        cors_allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-Request-ID"],
        cors_allow_credentials=False,
        cors_expose_headers=["X-Request-ID"],
    )


# Criados no import porque `@guard.rate_limit` decora as rotas quando o módulo carrega.
_config = security_config()
guard = SecurityDecorator(_config)

__all__ = ["guard", "security_config"]
