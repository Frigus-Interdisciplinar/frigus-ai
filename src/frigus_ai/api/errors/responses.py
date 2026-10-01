from pydantic import BaseModel

from frigus_ai.domain.errors import ErrorCode


class ErrorResponse(BaseModel):
    detail: str
    code: ErrorCode
    request_id: str | None = None


__all__ = ["ErrorResponse"]
