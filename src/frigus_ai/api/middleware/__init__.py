from fastapi import FastAPI
from guard import SecurityMiddleware

from frigus_ai.api.middleware.metrics import observar_http
from frigus_ai.api.middleware.request_id import propagar_request_id
from frigus_ai.api.middleware.security import _config, guard
from frigus_ai.settings import settings


def register_middlewares(app: FastAPI) -> None:
    app.middleware("http")(observar_http)
    if settings.api.key_auth_enabled:
        app.add_middleware(SecurityMiddleware, config=_config)
    # Por último = mais externo: roda antes de todos e o header sai até nas respostas do guard.
    app.middleware("http")(propagar_request_id)


__all__ = ["guard", "register_middlewares"]
