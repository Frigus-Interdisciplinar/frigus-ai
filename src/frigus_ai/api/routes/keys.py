"""
Emissão de API key. Protegida por `X-Signup-Secret` — sem cadastro aberto, que
neste projeto criaria usuário no Postgres pra qualquer um que chamasse a rota.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status

from frigus_ai.api.auth import verify_signup_secret
from frigus_ai.schemas.key import KeyCreate, KeyCreateResponse
from frigus_ai.services.api_key_service import api_key_service
from frigus_ai.services.user_service import user_service

router = APIRouter(
    prefix="/keys",
    tags=["keys"],
    dependencies=[Depends(verify_signup_secret)],
)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_key(payload: KeyCreate) -> KeyCreateResponse:
    user_id = await user_service.criar_usuario(payload.nome, payload.email)
    api_key = secrets.token_urlsafe(32)

    if not api_key_service.allocate_api_key(user_id, api_key):
        raise HTTPException(status.HTTP_409_CONFLICT, "Usuário já tem uma API key ativa.")

    return KeyCreateResponse(user_id=user_id, api_key=api_key)
