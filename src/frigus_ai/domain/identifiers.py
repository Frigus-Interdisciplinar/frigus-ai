from uuid import uuid4


def novo_chat_id() -> str:
    return str(uuid4())


__all__ = ["novo_chat_id"]
