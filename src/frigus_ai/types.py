"""
Tipos compartilhados entre camadas, sem dependência de services.

Só `Annotated[str/int, Field(...)]` — sem `NewType`: o projeto não roda type checker
(nem no CI, só `ruff`+`pytest`), então um `NewType` não pega troca de argumento
nenhuma, é decoração. O `Field(description=..., examples=...)` sim tem efeito real,
mas só onde vira schema Pydantic — por isso estes tipos existem para uso em
`schemas/*.py`, não em `repositories`/`services` (Python interno, nunca serializado).
"""

from typing import Annotated
from uuid import uuid4

from pydantic import Field

UserID = Annotated[
    int, 
    Field(
        description="Identificador único do usuário.", 
        examples=[42]
    )
]
ChatID = Annotated[
    str,
    Field(
        description="Identificador único do chat.",
        examples=["9979d729-681c-46ec-8741-b37fae55d9d7"],
    ),
]
APIKey = Annotated[
    str, 
    Field(
        description="Chave de API do usuário, usada no header X-API-Key.", 
        examples=["sk_live_51H8x..."]
    )
]


def novo_chat_id() -> str:
    return str(uuid4())


__all__ = [
    "APIKey", 
    "ChatID", 
    "UserID", 
    "novo_chat_id"
]
