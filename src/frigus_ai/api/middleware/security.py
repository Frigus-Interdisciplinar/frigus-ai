"""Configuração do fastapi-guard (rate limit, CORS) e o `guard` que decora as rotas."""

from guard import SecurityConfig, SecurityDecorator

from frigus_ai.settings import settings


def security_config() -> SecurityConfig:
    return SecurityConfig(
        redis_url=settings.database.redis_url,
        enable_rate_limiting=settings.api.key_auth_enabled,
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
