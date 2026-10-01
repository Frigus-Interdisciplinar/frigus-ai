"""Casos de uso de API key: alocação e resolução via Redis (hash, nunca a key em claro)."""

from frigus_ai.infra.logging import Logging
from frigus_ai.infra.redis.connection import get_client
from frigus_ai.infra.redis.keys import (
    API_KEY_TTL_TIME,
    _chave_api_key,
    _chave_api_key_lookup,
    _hash_api_key,
)
from frigus_ai.infra.redis.scripts import ALOCAR_KEY, REVOGAR_KEY, ROTACIONAR_KEY

logger = Logging.get_logger(__name__)


class AuthService:
    """Casos de uso de API key; a instância (`auth_service`, abaixo) é o ponto de entrada."""

    def allocate_api_key(self, user_id: str, api_key: str) -> bool:
        """
        Uma key ativa por usuário: o `nx=True` é o que garante isso — se já existe,
        devolve False em vez de sobrescrever (e deixar a key antiga órfã no lookup).
        """

        r = get_client()
        hashed = _hash_api_key(api_key)

        alocada = r.eval(
            ALOCAR_KEY, 2, _chave_api_key(user_id), _chave_api_key_lookup(hashed), hashed, user_id, API_KEY_TTL_TIME
        )
        if not alocada:
            logger.warning("Usuário %s já tem uma API key ativa.", user_id)
            return False

        logger.info("API key alocada para o usuário %s.", user_id)
        return True

    def rotate_api_key(self, user_id: str, nova_api_key: str) -> None:
        """Substitui a key ativa (ou cria, se não havia) sem janela em que as duas valem."""

        hashed = _hash_api_key(nova_api_key)
        get_client().eval(
            ROTACIONAR_KEY, 2, _chave_api_key(user_id), _chave_api_key_lookup(hashed),
            hashed, user_id, API_KEY_TTL_TIME, _chave_api_key_lookup(""),
        )
        logger.info("API key rotacionada para o usuário %s.", user_id)

    def revoke_api_key(self, user_id: str) -> bool:
        """False se o usuário não tinha key ativa."""

        revogada = bool(
            get_client().eval(REVOGAR_KEY, 1, _chave_api_key(user_id), _chave_api_key_lookup(""))
        )
        logger.info("API key do usuário %s %s.", user_id, "revogada" if revogada else "não existia")
        return revogada

    def get_user_id_by_api_key(self, api_key: str) -> str | None:
        user_id = get_client().get(_chave_api_key_lookup(_hash_api_key(api_key)))

        if user_id is None:
            logger.warning("API key não encontrada.")
            return None

        return user_id


auth_service = AuthService()
