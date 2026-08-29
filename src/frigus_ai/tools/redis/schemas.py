import hashlib

API_KEY_TTL_TIME = 3600 * 24 * 30
PROFILE_TTL_TIME = 3600
CHAT_TTL_TIME = 60
N_MESSAGES_ACCEPTED = 10


def _chave_perfil(user_id: int) -> str:
    return f"user:{user_id}:profile"


def _chave_mensagem(user_id: int) -> str:
    return f"chat:{user_id}:message"


def _hash_api_key(api_key: str) -> str:
    """Só o hash vai pro Redis — a key em claro existe uma vez, na resposta do POST /keys."""

    return hashlib.sha256(api_key.encode()).hexdigest()


def _chave_api_key(user_id: int) -> str:
    return f"auth:user:{user_id}:api-key-hash"


def _chave_api_key_lookup(hashed_key: str) -> str:
    return f"auth:api-key:{hashed_key}"
