"""Rotas de leitura de receitas — regras em `services/recipe_service.py`."""

from fastapi import APIRouter

from frigus_ai.api.deps import CurrentUserDep, RecipeServiceDep, StockIdDep
from frigus_ai.schemas.recipes import RecipeSuggestionResponse, RecipeSummaryResponse

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("")
async def list_recipes(
    user_id: CurrentUserDep, service: RecipeServiceDep, limit: int = 50
) -> list[RecipeSummaryResponse]:
    return await service.listar(limit)


@router.get("/suggestions")
async def recipe_suggestions(
    stock_id: StockIdDep, service: RecipeServiceDep, limit: int = 10
) -> list[RecipeSuggestionResponse]:
    return await service.sugerir(stock_id, limit)


__all__ = ["router"]
