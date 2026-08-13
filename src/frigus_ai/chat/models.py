from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    HUMAN = "human"
    AI = "ai"


@dataclass
class ChatMessage:
    role: Role
    content: str
