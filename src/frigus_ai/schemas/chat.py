from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from frigus_ai.domain.models import Role as DomainRole
from frigus_ai.domain.types import ChatID


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


_ROLE_MAP = {
    DomainRole.HUMAN: Role.USER,
    DomainRole.AI: Role.ASSISTANT,
}


class ChatCreateResponse(BaseModel):
    chat_id: ChatID
    stock_id: int | None


class MessageCreate(BaseModel):
    # extra="forbid": `stock_id` saiu do corpo (vinha sem checagem de dono); cliente antigo leva 422 em vez de ser ignorado.
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"content": "Quais receitas posso fazer hoje?"}]}
    )

    content: str = Field(min_length=1, max_length=4000, description="Mensagem para o assistente.")


class MessageResponse(BaseModel):
    role: Role
    content: str


class ChatMessageResponse(BaseModel):
    chat_id: ChatID
    content: str


class ChatSummaryResponse(BaseModel):
    chat_id: ChatID
    resume: str
    created_at: datetime
    updated_at: datetime
