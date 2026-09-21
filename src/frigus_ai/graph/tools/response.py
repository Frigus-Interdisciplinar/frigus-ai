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


__all__ = [
    "Response",
    "ResponseStatus",
    "ToolResponse",
    "ToolResponseError",
    "ToolResponseOk",
]