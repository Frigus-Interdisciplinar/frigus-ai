import asyncio

from langsmith import traceable

import frigus_ai.tools.mongo.chats.core as chats
import frigus_ai.tools.mongo.users.core as perfis
from frigus_ai.agents.nodes.guardrail.entrada import anonimizar_entrada
from frigus_ai.chat.models import ChatMessage, Role
from frigus_ai.tools.mongo.chats.schemas import Mensagem
from frigus_ai.tools.redis.perfil import (
    buscar_perfil_cache,
    invalidar_perfil_cache,
    salvar_perfil_cache,
)


def _para_mensagem(msg: ChatMessage) -> Mensagem:
    return Mensagem(role=msg.role, content=msg.content)


def _de_mensagem(msg: Mensagem) -> ChatMessage:
    return ChatMessage(role=Role(msg.role), content=msg.content)


def _mensagens_redigidas(mensagens: list[ChatMessage]) -> list[dict]:
    return [
        {"role": m.role.value, "content": anonimizar_entrada(m.content)[0]}
        for m in mensagens
    ]


def _redigir_saida_perfil(perfil: str | None) -> dict:
    texto, _ = anonimizar_entrada(perfil or "")
    return {"perfil": texto}


def _redigir_entrada_mensagens(inputs: dict) -> dict:
    redigido = dict(inputs)

    if "mensagens" in redigido:
        redigido["mensagens"] = _mensagens_redigidas(redigido["mensagens"])

    return redigido


def _redigir_saida_historico(historico: list[ChatMessage] | None) -> dict:
    return {"mensagens": _mensagens_redigidas(historico) if historico else []}


@traceable(run_type="tool", name="buscar_perfil", process_outputs=_redigir_saida_perfil)
async def buscar_perfil(user_id: int) -> str:
    """Cache-aside: tenta o Redis primeiro, só bate no Mongo em caso de miss."""

    perfil_cache = await asyncio.to_thread(buscar_perfil_cache, user_id)
    if perfil_cache is not None:
        return perfil_cache

    perfil = await asyncio.to_thread(perfis.buscar_perfil, user_id)
    await asyncio.to_thread(salvar_perfil_cache, user_id, perfil)
    return perfil


async def garantir_perfil(user_id: int) -> None:
    await asyncio.to_thread(perfis.garantir_perfil, user_id)


@traceable(
    run_type="tool", name="buscar_historico", process_outputs=_redigir_saida_historico
)
async def buscar_historico(
    session_id: str, user_id: int, limit: int = 5
) -> list[ChatMessage]:
    doc = await asyncio.to_thread(chats.buscar, session_id, user_id, limit=limit)
    if not doc:
        return []
    return [_de_mensagem(m) for m in Mensagem.de_dict(doc["messages"])]


@traceable(
    run_type="tool", name="salvar_mensagens", process_inputs=_redigir_entrada_mensagens
)
async def salvar_mensagens(
    user_id: int, session_id: str, mensagens: list[ChatMessage]
) -> None:
    mensagens_mongo = [_para_mensagem(m) for m in mensagens]
    await asyncio.to_thread(chats.adicionar_mensagens, session_id, user_id, mensagens_mongo)


async def encerrar_sessao(session_id: str, user_id: int) -> None:
    await asyncio.to_thread(chats.encerrar_sessao, session_id, user_id)
    await asyncio.to_thread(invalidar_perfil_cache, user_id)
