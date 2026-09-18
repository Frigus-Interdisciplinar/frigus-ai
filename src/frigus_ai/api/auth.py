"""
Auth por `X-API-Key`, mesmo desenho do assessor-ai: a key em claro nunca é
persistida — o Redis guarda `sha256(key) -> user_id` (`tools/redis/api_key.py`).
"""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from frigus_ai.services.api_key_service import api_key_service
from frigus_ai.services.user_service import user_service
from frigus_ai.settings import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_signup_secret_header = APIKeyHeader(name="X-Signup-Secret", auto_error=False)


async def resolver_usuario(api_key: str | None) -> int | None:
    """
    Quem é o dono da requisição, sem nada de FastAPI — o servidor MCP
    (`mcp/server.py`) monta como ASGI puro e chama isto direto.
    """

    if not settings.API_KEY_AUTH_ENABLED:
        # Auth desligada (modo local/demo): reaproveita ou cria o usuário local único,
        # sem depender de um id fixo. Ligue a flag pra exigir API key de verdade.
        return await user_service.obter_ou_criar_padrao()

    return api_key_service.get_user_id_by_api_key(api_key) if api_key else None


async def get_current_user(
    api_key: Annotated[str | None, Security(_api_key_header)] = None,
) -> int:
    if (user_id := await resolver_usuario(api_key)) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida.")

    return user_id


def verify_signup_secret(
    secret: Annotated[str | None, Security(_signup_secret_header)] = None,
) -> None:
    # Sem SIGNUP_SECRET configurado ninguém emite key — senão a rota de signup
    # ficaria aberta com secret vazio.
    if not settings.SIGNUP_SECRET or not secrets.compare_digest(
        secret or "", settings.SIGNUP_SECRET
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signup secret inválido.")


CurrentUserDep = Annotated[int, Depends(get_current_user)]
