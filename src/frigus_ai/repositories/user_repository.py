"""
Persistência crua de perfil de usuário: perfil comportamental no Mongo, cache do
perfil no Redis. Sem decisão de negócio — isso fica em `services/user_service.py`
(cache-aside). Identidade (Postgres) mora em `repositories/identidade_repository.py`.
"""

from datetime import UTC, datetime
from typing import TypedDict

from frigus_ai.infra.mongo.connection import mongo
from frigus_ai.infra.redis.connection import get_client
from frigus_ai.infra.redis.keys import PROFILE_TTL_TIME, _chave_perfil
from frigus_ai.logging import Logging

logger = Logging.get_logger(__name__)

collection = None


class UserProfileDocument(TypedDict):
    """Formato do documento em `user_profiles`."""

    user_id: int
    profile: str
    updated_at: datetime


class UserRepository:
    def _collection(self):
        return collection or mongo.collection("user_profiles")

    def buscar_perfil(self, user_id: int) -> str:
        logger.info(f"Buscando perfil comportamental para user_id: {user_id}")

        doc: UserProfileDocument | None = self._collection().find_one({"user_id": user_id})
        return doc.get("profile", "") if doc else ""

    def atualizar_perfil(self, user_id: int, perfil: str) -> None:
        logger.info(f"Atualizando perfil comportamental para user_id: {user_id}")

        self._collection().update_one(
            {"user_id": user_id},
            {"$set": {"profile": perfil, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )

    def garantir_perfil(self, user_id: int) -> None:
        self._collection().update_one(
            {"user_id": user_id},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "profile": "",
                    "updated_at": datetime.now(UTC),
                }
            },
            upsert=True,
        )

    def buscar_perfil_cache(self, user_id: int) -> str | None:
        valor = get_client().get(_chave_perfil(user_id))
        if valor is None:
            return None
        if isinstance(valor, bytes):
            return valor.decode("utf-8")
        return valor

    def salvar_perfil_cache(self, user_id: int, perfil: str) -> None:
        get_client().set(_chave_perfil(user_id), perfil, ex=PROFILE_TTL_TIME)

    def invalidar_perfil_cache(self, user_id: int) -> None:
        get_client().delete(_chave_perfil(user_id))


_user_repository = UserRepository()


def buscar_perfil(user_id: int) -> str:
    return _user_repository.buscar_perfil(user_id)


def atualizar_perfil(user_id: int, perfil: str) -> None:
    _user_repository.atualizar_perfil(user_id, perfil)


def garantir_perfil(user_id: int) -> None:
    _user_repository.garantir_perfil(user_id)


def buscar_perfil_cache(user_id: int) -> str | None:
    return _user_repository.buscar_perfil_cache(user_id)


def salvar_perfil_cache(user_id: int, perfil: str) -> None:
    _user_repository.salvar_perfil_cache(user_id, perfil)


def invalidar_perfil_cache(user_id: int) -> None:
    _user_repository.invalidar_perfil_cache(user_id)
