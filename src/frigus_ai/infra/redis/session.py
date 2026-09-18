from frigus_ai.infra.redis.connection import get_client
from frigus_ai.infra.redis.keys import SESSION_TTL_TIME, _chave_sessao


def buscar_usuario_da_sessao(context_id: str) -> int | None:
    valor = get_client().get(_chave_sessao(context_id))
    return int(valor) if valor is not None else None


def salvar_usuario_da_sessao(context_id: str, user_id: int) -> bool:
    """Salva somente se ainda não existir; o Redis faz a operação atomicamente."""

    return bool(
        get_client().set(
            _chave_sessao(context_id),
            user_id,
            ex=SESSION_TTL_TIME,
            nx=True,
        )
    )


__all__ = ["buscar_usuario_da_sessao", "salvar_usuario_da_sessao"]
