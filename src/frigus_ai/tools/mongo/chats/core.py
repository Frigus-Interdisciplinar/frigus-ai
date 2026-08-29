from datetime import UTC, datetime
from functools import lru_cache

import frigus_ai.tools.mongo.users.core as perfis
from config.logging import get_logger
from frigus_ai.tools.mongo.chats.schemas import Mensagem
from frigus_ai.tools.mongo.connection import banco
from frigus_ai.tools.mongo.helpers import _gerar_perfil, _gerar_resumo

logger = get_logger(__name__)

collection = banco["agent_chats"]


@lru_cache(maxsize=1)
def _garantir_indice() -> None:
    """
    Índice único em session_id: sem ele, dois upserts concorrentes no primeiro
    turno de uma sessão inserem dois documentos (o filtro não casa em nenhum dos
    dois). Criado sob demanda, não no import, para não abrir conexão com o Mongo
    só por importar o módulo.
    """

    collection.create_index("session_id", unique=True)


def buscar(session_id: str, user_id: int, limit: int = 5) -> dict | None:
    logger.info(f"Buscando histórico de mensagens para session_id: {session_id} (limit={limit})")

    return collection.find_one(
        {"session_id": session_id, "user_id": user_id},
        {"messages": {"$slice": -limit}}
    )


def adicionar_mensagens(session_id: str, user_id: int, mensagens: list[Mensagem]) -> None:
    """
    Upsert atômico: cria o documento no primeiro turno e faz `$push` nos demais.
    Substitui o antigo `buscar` -> `criar`/`atualizar`, que sob concorrência podia
    duplicar a sessão ou perder mensagens.
    """

    logger.info(f"Adicionando mensagens para session_id: {session_id}")

    _garantir_indice()
    agora = datetime.now(UTC)

    collection.update_one(
        {"session_id": session_id, "user_id": user_id},
        {
            "$push":        {"messages": {"$each": [m.para_dict() for m in mensagens]}},
            "$set":         {"updated_at": agora},
            "$setOnInsert": {"created_at": agora, "resume": ""},
        },
        upsert=True,
    )


def inserir_resumo(resumo: str, session_id: str, user_id: int) -> None:
    logger.info(f"Salvando resumo da sessão para session_id: {session_id}")

    collection.update_one(
        {"session_id": session_id, "user_id": user_id},
        {"$set": {"resume": resumo}}
    )


def encerrar_sessao(session_id: str, user_id: int) -> None:
    logger.info(f"Encerrando sessão para session_id: {session_id}")

    doc = collection.find_one({"session_id": session_id, "user_id": user_id})

    if not doc or not doc.get("messages"):
        return

    resumo = _gerar_resumo(doc["messages"])
    inserir_resumo(resumo, session_id, user_id)

    perfil_atual = perfis.buscar_perfil(user_id)
    perfil_atualizado = _gerar_perfil(perfil_atual, resumo)
    perfis.atualizar_perfil(user_id, perfil_atualizado)
