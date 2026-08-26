from frigus_ai.tools.redis.connection import get_client
from frigus_ai.tools.redis.schemas import PROFILE_TTL_TIME, _chave_perfil


def buscar_perfil_cache(user_id: int) -> str | None:
    r = get_client()
    chave = _chave_perfil(user_id)

    return r.get(chave)


def salvar_perfil_cache(user_id: int, perfil: str) -> None:
    r = get_client()
    chave = _chave_perfil(user_id)

    r.set(chave, perfil, ex=PROFILE_TTL_TIME)


def invalidar_perfil_cache(user_id: int) -> None:
    r = get_client()
    chave = _chave_perfil(user_id)

    r.delete(chave)
