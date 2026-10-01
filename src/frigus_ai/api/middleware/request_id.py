"""`X-Request-ID`: aceita o do cliente (validado) ou gera um, e propaga pra logs e respostas."""

import re
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from fastapi.responses import Response

from frigus_ai.infra.logging import request_id_var

type CallNext = Callable[[Request], Awaitable[Response]]

_REQUEST_ID_VALIDO = re.compile(r"[\w.-]{1,64}")


async def propagar_request_id(request: Request, call_next: CallNext) -> Response:
    recebido = request.headers.get("X-Request-ID", "")
    request_id = recebido if _REQUEST_ID_VALIDO.fullmatch(recebido) else str(uuid4())
    request.state.request_id = request_id
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


__all__ = ["propagar_request_id"]
