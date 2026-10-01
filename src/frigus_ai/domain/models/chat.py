"""Modelos de chat compartilhados entre services e schemas de API."""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    HUMAN = "human"
    AI = "ai"


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


__all__ = ["ChatMessage", "Role"]
