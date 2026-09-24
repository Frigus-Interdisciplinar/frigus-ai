"""
Subconjunto do A2A **1.0** que o cliente do Assessor usa: o envelope de `SendMessage` e a
resposta. Separado de `schemas/a2a.py`, que é o contrato 0.3 do servidor A2A do próprio Frigus
— as versões divergem em nome de método, `role` e `parts`.

Nomes de campo em snake_case, como o OpenAPI do Assessor publica. Na resposta só se lê
`message`/`task`/`parts`/`artifacts`/`status`/`text` — palavras sem `_`, então tanto faz se o
servidor serializa o protobuf em camelCase ou snake_case. Campo desconhecido é ignorado.
"""

from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _novo_id() -> str:
    return str(uuid4())


class Role(StrEnum):
    """Enum protobuf do A2A 1.0 (no 0.3 era `"user"`/`"agent"`)."""

    USER        = "ROLE_USER"
    AGENT       = "ROLE_AGENT"
    UNSPECIFIED = "ROLE_UNSPECIFIED"


class Part(BaseModel):
    text: str | None = None


def _texto(parts: list[Part]) -> str:
    return "\n".join(p.text for p in parts if p.text)


class Message(BaseModel):
    message_id: str = Field(default_factory=_novo_id)
    context_id: str | None = None
    role: Role
    parts: list[Part] = []

    def texto(self) -> str:
        return _texto(self.parts)


class SendMessageParams(BaseModel):
    message: Message


class SendMessageRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(default_factory=_novo_id)
    method: Literal["SendMessage"] = "SendMessage"
    params: SendMessageParams


class Artifact(BaseModel):
    parts: list[Part] = []


class TaskStatus(BaseModel):
    message: Message | None = None


class Task(BaseModel):
    artifacts: list[Artifact] = []
    status: TaskStatus | None = None

    def texto(self) -> str:
        """Artifacts são a resposta; sem eles, a mensagem de status (ex.: pedido de input)."""

        texto = "\n".join(t for t in (_texto(a.parts) for a in self.artifacts) if t)
        if texto or not (self.status and self.status.message):
            return texto
        return self.status.message.texto()


class SendMessageResult(BaseModel):
    """`oneof` do protobuf: vem `message` ou `task`, nunca os dois."""

    message: Message | None = None
    task: Task | None = None

    def texto(self) -> str:
        if self.message:
            return self.message.texto()
        return self.task.texto() if self.task else ""


class JsonRpcError(BaseModel):
    code: int
    message: str


class SendMessageResponse(BaseModel):
    result: SendMessageResult | None = None
    error: JsonRpcError | None = None


__all__ = [
    "Message",
    "Part",
    "Role",
    "SendMessageParams",
    "SendMessageRequest",
    "SendMessageResponse",
]
