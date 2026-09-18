"""Tipos compartilhados entre camadas, sem dependência de services."""

from typing import Annotated, NewType
from uuid import uuid4

from pydantic import Field

UserIDField = NewType("UserIDField", int)
ChatIDField = NewType("ChatIDField", str)
APIKeyField = NewType("APIKeyField", str)
APIKeyHash = NewType("APIKeyHash", str)

UserID = Annotated[
    UserIDField, 
    Field(
        description="Identificador único do usuário.", 
        examples=[42]
    )
]
ChatID = Annotated[
    ChatIDField,
    Field(
        description="Identificador único do chat.", 
        examples=["9979d729-681c-46ec-8741-b37fae55d9d7"]
    ),
]
APIKey = Annotated[
    APIKeyField,
    Field(
        description="Chave de API do usuário, usada no header X-API-Key.", 
        examples=["sk_live_51H8x..."]
    ),
]


def novo_chat_id() -> ChatID:
    return ChatID(str(uuid4()))


__all__ = [
    "APIKey",
    "APIKeyField",
    "APIKeyHash",
    "ChatID",
    "ChatIDField",
    "UserID",
    "UserIDField",
    "novo_chat_id",
]
