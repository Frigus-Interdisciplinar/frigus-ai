"""
Esqueleto de rotas de chat (ver TODO.md "API (FastAPI/Flask)"). Sem autenticação real ainda —
`user_id` é sempre `DEMO_USER_ID`, mesmo bootstrap usado por `interfaces/tui`, até "controle de
sessão por usuário de verdade" sair do TODO. `stock_id` é reresolvido a cada request (idempotente,
`iniciar_sessao` só faz um upsert) — trocar por sessão persistente quando a auth existir.
"""

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from frigus_ai.chat import service as chat_service
from frigus_ai.chat.models import Role as DomainRole
from interfaces.api.schemas.chat import (
    ChatCreateResponse,
    ChatMessageResponse,
    MessageCreate,
    MessageResponse,
    Role,
)

_ROLE_MAP = {
    DomainRole.HUMAN: Role.USER,
    DomainRole.AI: Role.ASSISTANT,
}

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_chat() -> ChatCreateResponse:
    chat_id = str(uuid4())
    stock_id = chat_service.iniciar_sessao(chat_service.DEMO_USER_ID)

    return ChatCreateResponse(chat_id=chat_id, stock_id=stock_id)


@router.post("/{chat_id}/messages")
def send_message(chat_id: str, payload: MessageCreate) -> ChatMessageResponse:
    user_id = chat_service.DEMO_USER_ID
    stock_id = chat_service.iniciar_sessao(user_id)

    try:
        resposta = chat_service.send_message(payload.content, chat_id, user_id, stock_id)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e)) from e

    return ChatMessageResponse(chat_id=chat_id, content=resposta)


@router.get("/{chat_id}/messages")
def get_messages(chat_id: str) -> list[MessageResponse]:
    historico = chat_service.get_history(chat_id)

    return [MessageResponse(role=_ROLE_MAP[m.role], content=m.content) for m in historico]
