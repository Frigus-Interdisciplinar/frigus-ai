"""
Esqueleto de rotas de chat (ver TODO.md "API (FastAPI/Flask)"). Sem autenticação real ainda —
`user_id` é sempre `DEMO_USER_ID`, mesmo bootstrap usado por `interfaces/tui`, até "controle de
sessão por usuário de verdade" sair do TODO. `stock_id` é reresolvido a cada request (idempotente,
`iniciar_sessao` só faz um upsert) — trocar por sessão persistente quando a auth existir.
"""

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from config.logging import get_logger
from frigus_ai.chat import service as chat_service
from frigus_ai.tools.redis.schemas import CHAT_TTL_TIME
from interfaces.api.schemas.chat import (
    _ROLE_MAP,
    ChatCreateResponse,
    ChatMessageResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/chats", tags=["chats"])
logger = get_logger(__name__)


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

    except chat_service.LimiteDeMensagensExcedido as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            str(e),
            headers={"Retry-After": str(CHAT_TTL_TIME)},
        ) from e

    # str(e) aqui vazaria mensagem interna (psycopg2/pymongo) pro cliente — o traceback
    # vai pro log, o cliente recebe texto genérico.
    except Exception as e:
        logger.exception("Falha ao processar mensagem | chat_id=%s", chat_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Erro interno ao processar a mensagem.") from e

    return ChatMessageResponse(chat_id=chat_id, content=resposta)


@router.get("/{chat_id}/messages")
async def get_messages(chat_id: str) -> list[MessageResponse]:
    historico = await chat_service.get_history(chat_id, chat_service.DEMO_USER_ID)

    return [
        MessageResponse(role=_ROLE_MAP[m.role], content=m.content)
        for m in historico
    ]


@router.delete("/{chat_id}", status_code=status.HTTP_202_ACCEPTED)
async def close_chat(chat_id: str, background_tasks: BackgroundTasks) -> None:
    """
    202 porque `encerrar_sessao` dispara duas chamadas de LLM (resumo da conversa +
    atualização do perfil) que ninguém precisa esperar — vão pro background.
    """

    background_tasks.add_task(
        chat_service.encerrar_sessao, 
        chat_id, 
        chat_service.DEMO_USER_ID
    )
