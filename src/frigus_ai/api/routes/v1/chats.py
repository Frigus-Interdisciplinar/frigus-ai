"""
Rotas de chat. `user_id` vem da auth (`api/auth/dependencies.py`); com
`API__KEY_AUTH_ENABLED=false` a dependência reaproveita/cria o usuário local único
(`user_service.obter_ou_criar_padrao`), mesmo bootstrap usado pela TUI. `stock_id`
é reresolvido a cada request (`OptionalStockIdDep`) — trocar por sessão persistente
quando houver sessão HTTP de verdade.

`LimiteDeMensagensExcedido` e qualquer outra exceção não tratada viram HTTP
em `api/errors/handlers.py`, registrado uma vez na app — não em try/except
aqui, mesma regra pra essa rota e pra `a2a.py`.
"""

from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from frigus_ai.api.deps import ChatServiceDep, CurrentUserDep, OptionalStockIdDep
from frigus_ai.schemas.chat import (
    _ROLE_MAP,
    ChatCreateResponse,
    ChatMessageResponse,
    ChatSummaryResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/chats", tags=["chats"])

ChatIdPath = Annotated[str, Path(description="Id do chat, devolvido por `POST /v1/chats`. Um id novo é criado no primeiro envio.")]


async def _dono_do_chat_dentro_do_limite(chat_id: ChatIdPath, user_id: CurrentUserDep, chat: ChatServiceDep) -> str:
    """
    Dono do chat + rate limit do caminho SSE. Vai numa dependência, e não no corpo da
    rota, porque o corpo de um gerador só roda depois que o status HTTP saiu — 403/429
    lá dentro seriam tarde demais. Aqui roda antes do stream abrir.

    Ownership antes do limite: request que vai levar 403 não deve consumir mensagem
    da janela do usuário.
    """

    await chat.validar_ownership(chat_id, user_id)
    await chat.garantir_limite(user_id)
    return user_id


DonoComLimiteDep = Annotated[str, Depends(_dono_do_chat_dentro_do_limite)]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Criar chat")
async def create_chat(user_id: CurrentUserDep, stock_id: OptionalStockIdDep, chat: ChatServiceDep) -> ChatCreateResponse:
    """Abre um chat novo e devolve o `chat_id`."""

    chat_id = await chat.criar_chat(user_id)

    return ChatCreateResponse(chat_id=chat_id, stock_id=stock_id)


@router.post(
    "/{chat_id}/messages",
    summary="Enviar mensagem",
    responses={
        403: {"description": "O chat não pertence ao usuário."},
        429: {"description": "Limite de mensagens excedido; ver `Retry-After`."},
    },
)
async def send_message(
    chat_id: ChatIdPath,
    payload: MessageCreate,
    user_id: CurrentUserDep,
    stock_id: OptionalStockIdDep,
    chat: ChatServiceDep,
) -> ChatMessageResponse:
    """
    Envia a mensagem ao assistente e devolve a resposta completa.
    `stock_id` no corpo sobrescreve o estoque padrão.
    """

    await chat.validar_ownership(chat_id, user_id)
    stock_id = payload.stock_id if payload.stock_id is not None else stock_id
    resposta = await chat.send_message(payload.content, chat_id, user_id, stock_id)

    return ChatMessageResponse(chat_id=chat_id, content=resposta)


@router.post(
    "/{chat_id}/messages/stream",
    response_class=EventSourceResponse,
    summary="Enviar mensagem (streaming SSE)",
    responses={
        403: {"description": "O chat não pertence ao usuário."},
        429: {"description": "Limite de mensagens excedido; ver `Retry-After`."},
    },
)
async def stream_message(
    chat_id: ChatIdPath,
    payload: MessageCreate,
    user_id: DonoComLimiteDep,
    stock_id: OptionalStockIdDep,
    chat: ChatServiceDep,
) -> AsyncIterable[ServerSentEvent]:
    """Timeline de execução do agente (`schemas/execution.py`) — um evento por
    node iniciado/concluído, rota escolhida e resposta final."""

    stock_id = payload.stock_id if payload.stock_id is not None else stock_id

    async for evento in chat.stream_message(payload.content, chat_id, user_id, stock_id):
        yield ServerSentEvent(data=evento, event=evento.type)


@router.get(
    "/{chat_id}/messages",
    summary="Histórico do chat",
    responses={
        403: {"description": "O chat não pertence ao usuário."},
    },
)
async def get_messages(
    chat_id: ChatIdPath,
    user_id: CurrentUserDep,
    chat: ChatServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 5,
) -> list[MessageResponse]:
    """Últimas `limit` mensagens (1–100, padrão 5). Chat inexistente devolve lista vazia."""

    await chat.validar_ownership(chat_id, user_id)
    historico = await chat.get_history(chat_id, user_id, limit)

    return [
        MessageResponse(role=_ROLE_MAP[m.role], content=m.content)
        for m in historico
    ]


@router.get("", summary="Listar chats")
async def list_chats(user_id: CurrentUserDep, chat: ChatServiceDep) -> list[ChatSummaryResponse]:
    """Chats do usuário, com resumo e datas."""

    chats = await chat.listar_chats(user_id)
    return [
        ChatSummaryResponse(
            chat_id=c["session_id"],
            resume=c.get("resume", ""),
            created_at=c["created_at"],
            updated_at=c["updated_at"],
        )
        for c in chats
    ]


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encerrar chat",
    responses={
        403: {"description": "O chat não pertence ao usuário."},
    },
)
async def close_chat(
    chat_id: ChatIdPath, user_id: CurrentUserDep, chat: ChatServiceDep, background_tasks: BackgroundTasks
) -> None:
    """
    202 porque `encerrar_sessao` pode disparar chamada de LLM (fatos/resumo do rabo
    de mensagens que o ciclo periódico ainda não cobriu, ver `_talvez_atualizar_memoria`)
    que ninguém precisa esperar — vai pro background.

    Ownership checado aqui, e não só dentro de `encerrar_sessao`: sem isso a rota
    devolve 202 mesmo pra chat de outro usuário — o valor não vaza (a busca é
    escopada por user_id), mas o status mente sobre o que aconteceu.
    """

    await chat.validar_ownership(chat_id, user_id)
    background_tasks.add_task(chat.encerrar_sessao, chat_id, user_id)


__all__ = ["router"]
