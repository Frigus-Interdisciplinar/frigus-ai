"""
Rotas de chat. `user_id` vem da auth (`interfaces/api/auth.py`); com
`API_KEY_AUTH_ENABLED=false` a dependência devolve o `DEMO_USER_ID`, mesmo
bootstrap usado por `interfaces/tui`. `stock_id` é reresolvido a cada request
(idempotente, `iniciar_sessao` só faz um upsert) — trocar por sessão persistente
quando houver sessão HTTP de verdade.

Nenhuma rota traduz `LimiteDeMensagensExcedido` nem erro inesperado: os dois têm
handler no app (`interfaces/api/main.py`).
"""

from collections.abc import AsyncIterable
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from frigus_ai.chat import service as chat_service
from interfaces.api.auth import CurrentUserDep, StockIdDep
from interfaces.api.schemas.chat import (
    _ROLE_MAP,
    ChatCreateResponse,
    ChatMessageResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/chats", tags=["chats"])


async def _usuario_dentro_do_limite(user_id: CurrentUserDep) -> int:
    """Rate limit do caminho SSE: o corpo de um gerador só roda depois que o status
    HTTP saiu, então levantar lá dentro seria tarde demais pro handler virar 429."""

    await chat_service.garantir_limite(user_id)
    return user_id


UsuarioComLimiteDep = Annotated[int, Depends(_usuario_dentro_do_limite)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_chat(stock_id: StockIdDep) -> ChatCreateResponse:
    return ChatCreateResponse(chat_id=str(uuid4()), stock_id=stock_id)


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str, payload: MessageCreate, user_id: CurrentUserDep, stock_id: StockIdDep
) -> ChatMessageResponse:
    resposta = await chat_service.send_message(payload.content, chat_id, user_id, stock_id)

    return ChatMessageResponse(chat_id=chat_id, content=resposta)


@router.post("/{chat_id}/messages/stream", response_class=EventSourceResponse)
async def stream_message(
    chat_id: str, payload: MessageCreate, user_id: UsuarioComLimiteDep, stock_id: StockIdDep
) -> AsyncIterable[ServerSentEvent]:
    """Um evento `no` por agente concluído, um evento `resposta` no fim."""

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
