"""
Quem faz a requisição: o login do app Frigus (ID token do Firebase em `Authorization: Bearer`) ou a
`X-API-Key`, para integrações. A key em claro nunca é persistida: o Redis guarda
`sha256(key) -> user_id` (`infra/redis/keys.py`).
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
    except (ValueError, firebase_auth.InvalidIdTokenError):
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
    Quem é o dono da requisição, sem nada de FastAPI — o servidor MCP (`api/mcp.py`) monta como
    ASGI puro e chama isto direto, só com a API key. `id_token` (Firebase) tem prioridade sobre a key.
    """

    if not settings.api.key_auth_enabled:
        # Auth desligada (modo local/demo): reaproveita ou cria o usuário local único.
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
    # Sem SIGNUP_SECRET configurado ninguém emite key, senão a rota ficaria aberta com secret vazio.
    esperado = settings.api_keys.signup_secret.get_secret_value()
    if not esperado or not secrets.compare_digest(secret or "", esperado):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signup secret inválido.")


CurrentUserDep = Annotated[str, Depends(get_current_user)]
