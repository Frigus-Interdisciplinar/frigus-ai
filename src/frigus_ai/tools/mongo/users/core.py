from datetime import UTC, datetime

from config.logging import get_logger
from frigus_ai.tools.mongo.connection import banco

logger = get_logger(__name__)

collection = banco["user_profiles"]


def buscar_perfil(user_id: int) -> str:
    logger.info(f"Buscando perfil comportamental para user_id: {user_id}")

    doc = collection.find_one({"user_id": user_id})
    return doc.get("profile", "") if doc else ""


def atualizar_perfil(user_id: int, perfil: str) -> None:
    logger.info(f"Atualizando perfil comportamental para user_id: {user_id}")

    collection.update_one(
        {"user_id": user_id},
        {"$set": {"profile": perfil, "updated_at": datetime.now(UTC)}},
        upsert=True,
    )


def garantir_perfil(user_id: int) -> None:
    collection.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {
            "user_id": user_id,
            "profile": "",
            "updated_at": datetime.now(UTC),
        }},
        upsert=True,
    )
