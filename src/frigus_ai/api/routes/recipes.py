"""Rotas de leitura de receitas — mesma camada de repository que a tool do LLM
(`graph/tools/receitas/repo.py`) usa. Sem escrita: sugestão é gerada, não editada."""

import asyncio

from fastapi import APIRouter

from frigus_ai.api.auth import CurrentUserDep
from frigus_ai.exceptions import EstoqueAtualNaoDefinido
from frigus_ai.repositories import receitas_repository
from frigus_ai.schemas.recipes import RecipeSuggestionResponse, RecipeSummaryResponse
from frigus_ai.services.user_service import user_service

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("")
async def list_recipes(user_id: CurrentUserDep, limit: int = 50) -> list[RecipeSummaryResponse]:
    receitas = await asyncio.to_thread(receitas_repository.listar_receitas, limit)

    return [RecipeSummaryResponse(**receita) for receita in receitas]


@router.get("/suggestions")
async def recipe_suggestions(
    user_id: CurrentUserDep, limit: int = 10
) -> list[RecipeSuggestionResponse]:
    stock_id = await user_service.resolver_stock_id(user_id)
    if stock_id is None:
        raise EstoqueAtualNaoDefinido

    sugestoes = await asyncio.to_thread(receitas_repository.match_recipes_to_stock, stock_id, limit)

    return [RecipeSuggestionResponse(**sugestao) for sugestao in sugestoes]


__all__ = ["router"]
