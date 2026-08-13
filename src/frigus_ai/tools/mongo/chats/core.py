from dataclasses import asdict
from datetime import datetime, timezone

from frigus_ai.tools.mongo.helpers import _gerar_resumo, _gerar_perfil
from frigus_ai.tools.mongo.connection import banco
from frigus_ai.tools.mongo.chats.schemas import ChatDocument, Mensagem
from config.logging import get_logger

import frigus_ai.tools.mongo.users.core as perfis

logger = get_logger(__name__)

collection = banco["agent_chats"]


def criar(user_id: int, session_id: str, mensagens: list[Mensagem]) -> None:
    logger.info(f"Criando novo histórico de chat para session_id: {session_id}")

    document = ChatDocument(
        user_id=user_id,
        session_id=session_id,
        messages=[m.para_dict() for m in mensagens],
    )
    collection.insert_one(asdict(document))


def buscar(session_id: str, limit: int = 5) -> dict | None:
    logger.info(f"Buscando histórico de mensagens para session_id: {session_id} (limit={limit})")

    return collection.find_one(
        {"session_id": session_id},
        {"messages": {"$slice": -limit}}
    )


def atualizar_mensagens(session_id: str, mensagens_novas: list[Mensagem]) -> None:
    logger.info(f"Adicionando mensagens para session_id: {session_id}")

    collection.update_one(
        {"session_id": session_id},
        {
            "$push": {"messages": {"$each": [m.para_dict() for m in mensagens_novas]}},
            "$set":  {"updated_at": datetime.now(timezone.utc)},
        }
    )


def inserir_resumo(resumo: str, session_id: str) -> None:
    logger.info(f"Salvando resumo da sessão para session_id: {session_id}")

    collection.update_one(
        {"session_id": session_id},
        {"$set": {"resume": resumo}}
    )


def encerrar_sessao(session_id: str, user_id: int) -> None:
    logger.info(f"Encerrando sessão para session_id: {session_id}")

    doc = collection.find_one({"session_id": session_id})

    if not doc or not doc.get("messages"):
        return

    resumo = _gerar_resumo(doc["messages"])
    inserir_resumo(resumo, session_id)

    perfil_atual = perfis.buscar_perfil(user_id)
    perfil_atualizado = _gerar_perfil(perfil_atual, resumo)
    perfis.atualizar_perfil(user_id, perfil_atualizado)
