from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from frigus_ai.schemas.models import Role as DomainRole
from frigus_ai.types import ChatID


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
    content: str = Field(min_length=1, max_length=4000)


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
