"""
Emissão, rotação e revogação de API key. A emissão é protegida por `X-Signup-Secret` — sem
cadastro aberto, que neste projeto criaria usuário no Postgres pra qualquer um que chamasse a
rota. Rotação e revogação são do próprio dono: autenticadas pela key atual (`X-API-Key`).
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status

from frigus_ai.api.auth import verify_signup_secret
from frigus_ai.api.auth.schemas import KeyCreate, KeyCreateResponse
from frigus_ai.api.deps import AuthServiceDep, CurrentUserDep, UserServiceDep
from frigus_ai.api.middleware import guard

router = APIRouter(prefix="/keys", tags=["keys"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_signup_secret)],
    summary="Criar API key",
    responses={
        401: {"description": "`X-Signup-Secret` ausente ou errado (ou não configurado no servidor)."},
        409: {"description": "O usuário já tem uma API key ativa — use `/keys/rotate`."},
        429: {"description": "Limite de 5 requisições por hora por IP."},
    },
)
@guard.rate_limit(requests=5, window=3600)  # por IP: freia chute do signup secret
async def create_key(
    payload: KeyCreate, users: UserServiceDep, auth: AuthServiceDep
) -> KeyCreateResponse:
    """
    Cria o usuário (idempotente por email) e emite a API key, devolvida **uma única vez**.
    Exige o header `X-Signup-Secret`.
    """

    user_id = await users.criar_usuario(payload.nome, payload.email)
    api_key = secrets.token_urlsafe(32)

    if not auth.allocate_api_key(user_id, api_key):
        raise HTTPException(status.HTTP_409_CONFLICT, "Usuário já tem uma API key ativa.")

    return KeyCreateResponse(user_id=user_id, api_key=api_key)


@router.post(
    "/rotate",
    summary="Rotacionar API key",
    responses={
        401: {"description": "API key inválida."},
        429: {"description": "Limite de 5 por hora."},
    },
)
@guard.rate_limit(requests=5, window=3600)
async def rotate_key(user_id: CurrentUserDep, auth: AuthServiceDep) -> KeyCreateResponse:
    """Troca a key atual por uma nova; a antiga deixa de valer na hora."""

    api_key = secrets.token_urlsafe(32)
    auth.rotate_api_key(user_id, api_key)

    return KeyCreateResponse(user_id=user_id, api_key=api_key)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revogar API key",
    responses={
        401: {"description": "API key inválida."},
        429: {"description": "Limite de 5 por hora."},
    },
)
@guard.rate_limit(requests=5, window=3600)
async def revoke_key(user_id: CurrentUserDep, auth: AuthServiceDep) -> None:
    """Revoga a key atual; ela deixa de valer na hora."""

    auth.revoke_api_key(user_id)


__all__ = ["router"]
