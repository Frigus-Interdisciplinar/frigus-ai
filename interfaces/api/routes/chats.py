"""
Esqueleto de rotas de chat (ver TODO.md "API (FastAPI/Flask)"). Sem autenticação real ainda —
`user_id` é sempre `DEMO_USER_ID`, mesmo bootstrap usado por `interfaces/tui`, até "controle de
sessão por usuário de verdade" sair do TODO. `stock_id` é reresolvido a cada request (idempotente,
`iniciar_sessao` só faz um upsert) — trocar por sessão persistente quando a auth existir.
"""

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from frigus_ai.chat import service as chat_service
from interfaces.api.schemas.chat import (
    _ROLE_MAP,
    ChatCreateResponse,
    ChatMessageResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_chat() -> ChatCreateResponse:
    chat_id = str(uuid4())
    stock_id = await chat_service.iniciar_sessao(chat_service.DEMO_USER_ID)

    return ChatCreateResponse(chat_id=chat_id, stock_id=stock_id)


@router.post("/{chat_id}/messages")
async def send_message(chat_id: str, payload: MessageCreate) -> ChatMessageResponse:
    user_id = chat_service.DEMO_USER_ID
    stock_id = await chat_service.iniciar_sessao(user_id)

    try:
        resposta = await chat_service.send_message(
            payload.content, 
            chat_id, 
            user_id, 
            stock_id
        )
        
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e)) from e

    return ChatMessageResponse(chat_id=chat_id, content=resposta)


@router.get("/{chat_id}/messages")
async def get_messages(chat_id: str) -> list[MessageResponse]:
    historico = await chat_service.get_history(chat_id)

    return [
        MessageResponse(role=_ROLE_MAP[m.role], content=m.content) 
        for m in historico
    ]
