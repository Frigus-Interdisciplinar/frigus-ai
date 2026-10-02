"""
Auth por `X-API-Key`, mesmo desenho do assessor-ai: a key em claro nunca é
persistida — o Redis guarda `sha256(key) -> user_id` (`tools/redis/api_key.py`).
"""

import asyncio
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from frigus_ai.services.auth_service import auth_service
from frigus_ai.services.user_service import user_service
from frigus_ai.settings import settings

_api_key_header = APIKeyHeader(name="X-API-Key", scheme_name="ApiKey", auto_error=False)
_signup_secret_header = APIKeyHeader(name="X-Signup-Secret", scheme_name="SignupSecret", auto_error=False)


async def resolver_usuario(api_key: str | None) -> str | None:
    """
    Quem é o dono da requisição, sem nada de FastAPI — o servidor MCP
    (`mcp/server.py`) monta como ASGI puro e chama isto direto.
    """

    if not settings.api.key_auth_enabled:
        # Auth desligada (modo local/demo): reaproveita ou cria o usuário local único,
        # sem depender de um id fixo. Ligue a flag pra exigir API key de verdade.
        return await user_service.obter_ou_criar_padrao()

    if not api_key:
        return None

    return await asyncio.to_thread(auth_service.get_user_id_by_api_key, api_key)


async def get_current_user(
    api_key: Annotated[str | None, Security(_api_key_header)] = None,
) -> str:
    if (user_id := await resolver_usuario(api_key)) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida.")

    return user_id


def verify_signup_secret(
    secret: Annotated[str | None, Security(_signup_secret_header)] = None,
) -> None:
    # Sem SIGNUP_SECRET configurado ninguém emite key — senão a rota de signup
    # ficaria aberta com secret vazio.
    esperado = settings.api_keys.signup_secret.get_secret_value()
    if not esperado or not secrets.compare_digest(secret or "", esperado):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signup secret inválido.")


CurrentUserDep = Annotated[str, Depends(get_current_user)]
