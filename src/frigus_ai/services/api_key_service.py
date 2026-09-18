"""Casos de uso de API key: alocação e resolução via Redis (hash, nunca a key em claro)."""

from frigus_ai.infra.redis.connection import get_client
from frigus_ai.infra.redis.keys import (
    API_KEY_TTL_TIME,
    _chave_api_key,
    _chave_api_key_lookup,
    _hash_api_key,
)
from frigus_ai.logging import Logging

logger = Logging.get_logger(__name__)


class ApiKeyService:
    """Casos de uso de API key; a instância (`api_key_service`, abaixo) é o ponto de entrada."""

    def allocate_api_key(self, user_id: int, api_key: str) -> bool:
        """
        Uma key ativa por usuário: o `nx=True` é o que garante isso — se já existe,
        devolve False em vez de sobrescrever (e deixar a key antiga órfã no lookup).
        """

        r = get_client()
        hashed = _hash_api_key(api_key)

        if not r.set(_chave_api_key(user_id), hashed, ex=API_KEY_TTL_TIME, nx=True):
            logger.warning(f"Usuário {user_id} já tem uma API key ativa.")
            return False

        r.set(_chave_api_key_lookup(hashed), user_id, ex=API_KEY_TTL_TIME)

        logger.info(f"API key alocada para o usuário {user_id}.")
        return True

    def get_user_id_by_api_key(self, api_key: str) -> int | None:
        user_id = get_client().get(_chave_api_key_lookup(_hash_api_key(api_key)))

        if user_id is None:
            logger.warning("API key não encontrada.")
            return None

        return int(user_id)


api_key_service = ApiKeyService()
