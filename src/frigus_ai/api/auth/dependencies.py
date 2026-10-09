"""
Auth por `X-API-Key`, mesmo desenho do assessor-ai: a key em claro nunca é
persistida — o Redis guarda `sha256(key) -> user_id` (`tools/redis/api_key.py`).
"""

import asyncio
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from frigus_ai.infra.firebase import get_firebase_app
from frigus_ai.repositories import identidade_repository
from frigus_ai.services.auth_service import auth_service
from frigus_ai.services.user_service import user_service
from frigus_ai.settings import settings

_api_key_header = APIKeyHeader(name="X-API-Key", scheme_name="ApiKey", auto_error=False)
_bearer = HTTPBearer(scheme_name="FirebaseToken", auto_error=False)
_signup_secret_header = APIKeyHeader(
    name="X-Signup-Secret", scheme_name="SignupSecret", auto_error=False
)


def _usuario_do_firebase(id_token: str) -> str | None:
    """ID token do Firebase -> user_id no Postgres (casado por email, criado no 1º login)."""

    try:
        claims = firebase_auth.verify_id_token(id_token, app=get_firebase_app())
    except (ValueError, firebase_auth.AuthError):
        return None

    if not claims.get("email") or not claims.get("email_verified"):
        return None

    return identidade_repository.criar_usuario(
        claims.get("name") or claims["email"], claims["email"]
    )


async def resolver_usuario(
    api_key: str | None, id_token: str | None = None
) -> str | None:
    """
    Quem é o dono da requisição, sem nada de FastAPI — o servidor MCP
    (`mcp/server.py`) monta como ASGI puro e chama isto direto. `id_token` (Firebase,
    `Authorization: Bearer`) tem prioridade; a API key segue valendo (MCP/A2A/máquinas).
    """

    if not settings.api.key_auth_enabled:
        # Auth desligada (modo local/demo): reaproveita ou cria o usuário local único,
        # sem depender de um id fixo. Ligue a flag pra exigir API key de verdade.
        return await user_service.obter_ou_criar_padrao()

    if id_token:
        return await asyncio.to_thread(_usuario_do_firebase, id_token)

    if not api_key:
        return None

    return await asyncio.to_thread(auth_service.get_user_id_by_api_key, api_key)


async def get_current_user(
    api_key: Annotated[str | None, Security(_api_key_header)] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)] = None,
) -> str:
    if (
        user_id := await resolver_usuario(api_key, bearer and bearer.credentials)
    ) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credencial inválida.")

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
