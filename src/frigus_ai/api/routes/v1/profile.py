"""
Perfil alimentar estruturado (alergias, preferências, restrições, hábitos) — mesma
coleção (`user_fatos`) que a extração automática do chat lê e atualiza
(`services/chat_service.py`). `PUT` é o único caminho que pode remover uma alergia:
a extração automática só adiciona (`user_service.atualizar_fatos_por_extracao`).
"""

from fastapi import APIRouter

from frigus_ai.api.deps import CurrentUserDep, UserServiceDep
from frigus_ai.domain.models import Fatos, RecipePreferences, RecipePreferencesPatch

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", summary="Ver perfil alimentar")
async def get_profile(user_id: CurrentUserDep, service: UserServiceDep) -> Fatos:
    return await service.buscar_fatos(user_id)


@router.put(
    "",
    summary="Atualizar perfil alimentar",
)
async def update_profile(payload: Fatos, user_id: CurrentUserDep, service: UserServiceDep) -> Fatos:
    """Substitui o perfil inteiro; é o único caminho que remove uma alergia."""

    await service.sobrescrever_fatos(user_id, payload)
    return payload


@router.get("/recipe-preferences", summary="Ver preferências de receitas")
async def get_recipe_preferences(user_id: CurrentUserDep, service: UserServiceDep) -> RecipePreferences:
    return await service.buscar_preferencias_receitas(user_id)


@router.patch("/recipe-preferences", summary="Atualizar preferências de receitas")
async def update_recipe_preferences(
    payload: RecipePreferencesPatch, user_id: CurrentUserDep, service: UserServiceDep
) -> RecipePreferences:
    """Atualização parcial: campo ausente ou `null` não muda; `restricoes: []` limpa a lista."""

    return await service.atualizar_preferencias_receitas(user_id, payload)


__all__ = ["router"]
