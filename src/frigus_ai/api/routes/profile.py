"""
Perfil alimentar estruturado (alergias, preferências, restrições, hábitos) — mesma
coleção (`user_fatos`) que a extração automática do chat lê e atualiza
(`services/chat_service.py`). `PUT` é o único caminho que pode remover uma alergia:
a extração automática só adiciona (`user_service.atualizar_fatos_por_extracao`).
"""

from fastapi import APIRouter

from frigus_ai.api.auth import CurrentUserDep
from frigus_ai.schemas.models import Fatos
from frigus_ai.services.user_service import user_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_profile(user_id: CurrentUserDep) -> Fatos:
    return await user_service.buscar_fatos(user_id)


@router.put("")
async def update_profile(payload: Fatos, user_id: CurrentUserDep) -> Fatos:
    await user_service.sobrescrever_fatos(user_id, payload)
    return payload


__all__ = ["router"]
