"""
Rotas de chat. `user_id` vem da auth (`interfaces/api/auth.py`); com
`API_KEY_AUTH_ENABLED=false` a dependência devolve o `DEMO_USER_ID`, mesmo
bootstrap usado por `interfaces/tui`. `stock_id` é reresolvido a cada request
(idempotente, `iniciar_sessao` só faz um upsert) — trocar por sessão persistente
quando houver sessão HTTP de verdade.
"""

from collections.abc import AsyncIterable
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from config.logging import get_logger
from frigus_ai.chat import service as chat_service
from frigus_ai.tools.redis.schemas import CHAT_TTL_TIME
from interfaces.api.auth import CurrentUserDep
from interfaces.api.schemas.chat import (
    _ROLE_MAP,
    ChatCreateResponse,
    ChatMessageResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/chats", tags=["chats"])
logger = get_logger(__name__)

_LIMITE_HEADERS = {"Retry-After": str(CHAT_TTL_TIME)}


async def _usuario_dentro_do_limite(user_id: CurrentUserDep) -> int:
    """Rate limit do caminho SSE: o corpo de um gerador só roda depois que o status
    HTTP saiu, então 429 lá dentro seria tarde demais. Aqui roda antes do stream abrir."""

    try:
        await chat_service.garantir_limite(user_id)
    except chat_service.LimiteDeMensagensExcedido as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, str(e), headers=_LIMITE_HEADERS
        ) from e

    return user_id


UsuarioComLimiteDep = Annotated[int, Depends(_usuario_dentro_do_limite)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_chat(user_id: CurrentUserDep) -> ChatCreateResponse:
    chat_id = str(uuid4())
    stock_id = await chat_service.iniciar_sessao(user_id)

    return ChatCreateResponse(chat_id=chat_id, stock_id=stock_id)


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str, payload: MessageCreate, user_id: CurrentUserDep
) -> ChatMessageResponse:
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
            status.HTTP_429_TOO_MANY_REQUESTS, str(e), headers=_LIMITE_HEADERS
        ) from e

    # str(e) aqui vazaria mensagem interna (psycopg2/pymongo) pro cliente — o traceback
    # vai pro log, o cliente recebe texto genérico.
    except Exception as e:
        logger.exception("Falha ao processar mensagem | chat_id=%s", chat_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Erro interno ao processar a mensagem.") from e

    return ChatMessageResponse(chat_id=chat_id, content=resposta)


@router.post("/{chat_id}/messages/stream", response_class=EventSourceResponse)
async def stream_message(
    chat_id: str, payload: MessageCreate, user_id: UsuarioComLimiteDep
) -> AsyncIterable[ServerSentEvent]:
    """Um evento `no` por agente concluído, um evento `resposta` no fim."""

    stock_id = await chat_service.iniciar_sessao(user_id)

    async for tipo, valor in chat_service.stream_message(
        payload.content, chat_id, user_id, stock_id
    ):
        yield ServerSentEvent(data={tipo: valor}, event=tipo)


@router.get("/{chat_id}/messages")
async def get_messages(chat_id: str, user_id: CurrentUserDep) -> list[MessageResponse]:
    historico = await chat_service.get_history(chat_id, user_id)

    return [
        MessageResponse(role=_ROLE_MAP[m.role], content=m.content)
        for m in historico
    ]


@router.delete("/{chat_id}", status_code=status.HTTP_202_ACCEPTED)
async def close_chat(
    chat_id: str, user_id: CurrentUserDep, background_tasks: BackgroundTasks
) -> None:
    """
    202 porque `encerrar_sessao` dispara duas chamadas de LLM (resumo da conversa +
    atualização do perfil) que ninguém precisa esperar — vão pro background.
    """

    background_tasks.add_task(chat_service.encerrar_sessao, chat_id, user_id)
