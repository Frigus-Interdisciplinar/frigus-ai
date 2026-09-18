"""
Rotas de chat. `user_id` vem da auth (`api/auth.py`); com
`API_KEY_AUTH_ENABLED=false` a dependência reaproveita/cria o usuário local único
(`user_service.obter_ou_criar_padrao`), mesmo bootstrap usado pela TUI. `stock_id`
é reresolvido a cada request
(idempotente, `iniciar_sessao` só faz um upsert) — trocar por sessão persistente
quando houver sessão HTTP de verdade.

`LimiteDeMensagensExcedido` e qualquer outra exceção não tratada viram HTTP
em `api/exception_handler.py`, registrado uma vez na app — não em try/except
aqui, mesma regra pra essa rota e pra `a2a.py`.
"""

from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from frigus_ai.api.auth import CurrentUserDep
from frigus_ai.schemas.chat import (
    _ROLE_MAP,
    ChatCreateResponse,
    ChatMessageResponse,
    MessageCreate,
    MessageResponse,
)
from frigus_ai.services.chat_service import service as chat_service

router = APIRouter(prefix="/chats", tags=["chats"])


async def _usuario_dentro_do_limite(user_id: CurrentUserDep) -> int:
    """Rate limit do caminho SSE: o corpo de um gerador só roda depois que o status
    HTTP saiu, então 429 lá dentro seria tarde demais. Aqui roda antes do stream abrir."""

    await chat_service.garantir_limite(user_id)
    return user_id


UsuarioComLimiteDep = Annotated[int, Depends(_usuario_dentro_do_limite)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_chat(user_id: CurrentUserDep) -> ChatCreateResponse:
    chat_id = await chat_service.criar_chat(user_id)
    stock_id = await chat_service.iniciar_sessao(user_id)

    return ChatCreateResponse(chat_id=chat_id, stock_id=stock_id)


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str, payload: MessageCreate, user_id: CurrentUserDep
) -> ChatMessageResponse:
    await chat_service.validar_ownership(chat_id, user_id)
    stock_id = await chat_service.iniciar_sessao(user_id)
    resposta = await chat_service.send_message(payload.content, chat_id, user_id, stock_id)

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
    await chat_service.validar_ownership(chat_id, user_id)
    historico = await chat_service.get_history(chat_id, user_id)

    return [
        MessageResponse(role=_ROLE_MAP[m.role], content=m.content)
        for m in historico
    ]


@router.get("")
async def list_chats(user_id: CurrentUserDep) -> list[dict]:
    return await chat_service.listar_chats(user_id)


@router.delete("/{chat_id}", status_code=status.HTTP_202_ACCEPTED)
async def close_chat(
    chat_id: str, user_id: CurrentUserDep, background_tasks: BackgroundTasks
) -> None:
    """
    202 porque `encerrar_sessao` dispara duas chamadas de LLM (resumo da conversa +
    atualização do perfil) que ninguém precisa esperar — vão pro background.
    """

    background_tasks.add_task(chat_service.encerrar_sessao, chat_id, user_id)
