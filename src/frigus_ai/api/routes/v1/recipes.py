"""Rotas de leitura de receitas — regras em `services/recipe_service.py`."""

from typing import Literal

from fastapi import APIRouter, status

from frigus_ai.api.deps import CurrentUserDep, RecipeServiceDep, StockIdDep
from frigus_ai.schemas.recipes import (
    RecipeDetailResponse,
    RecipeSuggestionResponse,
    RecipeSummaryResponse,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", summary="Listar receitas")
async def list_recipes(
    user_id: CurrentUserDep, service: RecipeServiceDep, limit: int = 50, query: str | None = None
) -> list[RecipeSummaryResponse]:
    """Até `limit` receitas (padrão 50); `query` filtra pelo nome."""

    return await service.listar(user_id, limit, query)


@router.get(
    "/suggestions",
    summary="Sugerir receitas",
)
async def recipe_suggestions(
    user_id: CurrentUserDep, stock_id: StockIdDep, service: RecipeServiceDep, limit: int = 10
) -> list[RecipeSuggestionResponse]:
    """
    Receitas que combinam com o estoque atual, até `limit` (padrão 10). Ingrediente que vence em
    breve sobe a receita no ranking; alergias do perfil excluem a receita. Restrições alimentares
    ainda não são verificadas por receita e voltam em `unverified_restrictions`.
    """

    return await service.sugerir(user_id, stock_id, limit)


@router.get("/favorites", summary="Listar receitas favoritas")
async def list_favorites(
    user_id: CurrentUserDep, service: RecipeServiceDep, limit: int = 20
) -> list[RecipeSummaryResponse]:
    return await service.favoritas(user_id, limit)


# Declarada depois de `/suggestions`, que senão seria capturada como `source`.
@router.get("/{source}/{recipe_id}", summary="Detalhar receita")
async def recipe_detail(
    user_id: CurrentUserDep,
    service: RecipeServiceDep,
    source: Literal["local", "spoonacular"],
    recipe_id: int,
    include_nutrition: bool = False,
) -> RecipeDetailResponse:
    """Ingredientes, preparo e créditos; nutrição (por porção) só se pedida."""

    return await service.detalhar(user_id, source, recipe_id, include_nutrition)


@router.put(
    "/{source}/{recipe_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Favoritar receita",
)
async def favorite_recipe(
    user_id: CurrentUserDep, service: RecipeServiceDep, source: Literal["local", "spoonacular"], recipe_id: int
) -> None:
    """Idempotente: favoritar de novo mantém um único registro."""

    await service.favoritar(user_id, source, recipe_id)


@router.delete(
    "/{source}/{recipe_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desfavoritar receita",
)
async def unfavorite_recipe(
    user_id: CurrentUserDep, service: RecipeServiceDep, source: Literal["local", "spoonacular"], recipe_id: int
) -> None:
    await service.desfavoritar(user_id, source, recipe_id)


__all__ = ["router"]
