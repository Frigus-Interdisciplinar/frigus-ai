import functools
import inspect
from collections.abc import Callable
from enum import StrEnum
from typing import Literal, TypedDict


class ResponseStatus(StrEnum):
    OK = "ok"
    ERROR = "error"

class ToolResponseError(TypedDict):
    status: Literal[ResponseStatus.ERROR]
    message: str

type ToolResponseOk = dict[str, object]

type ToolResponse = ToolResponseOk | ToolResponseError


class Response:
    @staticmethod
    def ok(**kwargs: object) -> ToolResponseOk:
        return {"status": ResponseStatus.OK, **kwargs}

    @staticmethod
    def error(message: Exception | str) -> ToolResponseError:
        return {"status": ResponseStatus.ERROR, "message": str(message)}

    @staticmethod
    def catch[**P](func: Callable[P, ToolResponse]) -> Callable[P, ToolResponse]:
        """Converte qualquer exception que a tool levantar em `Response.error` — tira o
        `try/except` repetido de cada método. `log_classe`/`log_tool` já loga
        CHAMANDO/OK/ERRO com o nome do método e o tempo decorrido, então o método em si
        não precisa logar nada.

        Preserva sync/async: `log_tool`, aplicado por cima via `ToolSet`, decide qual
        wrapper usar com `inspect.iscoroutinefunction` — se aqui sempre devolvesse uma
        função sync (mesmo embrulhando um método `async def`), `log_tool` acharia que é
        síncrono, chamaria sem `await` e logaria "OK" com a coroutine ainda por rodar.
        """

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> ToolResponse:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    return Response.error(e)

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> ToolResponse:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return Response.error(e)

        return wrapper


__all__ = [
    "Response",
    "ResponseStatus",
    "ToolResponse",
    "ToolResponseError",
    "ToolResponseOk",
]