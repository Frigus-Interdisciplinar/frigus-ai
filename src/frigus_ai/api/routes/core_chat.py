import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from frigus_ai.schemas.core_chat import CoreChatRequest, CoreChatResponse
from frigus_ai.services.core_chat_service import core_chat_service
from frigus_ai.settings import settings

_service_key = APIKeyHeader(name="X-Core-Service-Key", auto_error=False)


def exigir_core(key: Annotated[str | None, Security(_service_key)] = None) -> None:
    esperado = settings.api_keys.core_service_key.get_secret_value()
    if len(esperado) < 32 or not secrets.compare_digest((key or "").encode(), esperado.encode()):
        raise HTTPException(401, "Credencial de serviço inválida.")


router = APIRouter(prefix="/internal/core", tags=["Core"], dependencies=[Depends(exigir_core)])


@router.post("/chat")
async def conversar(pedido: CoreChatRequest) -> CoreChatResponse:
    return await core_chat_service.conversar(pedido)
