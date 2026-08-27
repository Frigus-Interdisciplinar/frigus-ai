from enum import StrEnum

from pydantic import BaseModel, Field

from frigus_ai.chat.models import Role
from frigus_ai.chat.models import Role as DomainRole

_ROLE_MAP = {
    DomainRole.HUMAN: Role.USER,
    DomainRole.AI: Role.ASSISTANT,
}

class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatCreateResponse(BaseModel):
    chat_id: str
    stock_id: int | None


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    role: Role
    content: str


class ChatMessageResponse(BaseModel):
    chat_id: str
    content: str
