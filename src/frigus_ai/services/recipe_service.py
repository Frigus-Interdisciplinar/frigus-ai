"""Casos de uso de leitura de receitas. Sem escrita: sugestão é gerada, não editada."""

import asyncio

from frigus_ai.repositories import receitas_repository
from frigus_ai.schemas.recipes import RecipeSuggestionResponse, RecipeSummaryResponse


class RecipeService:
    async def listar(self, limit: int) -> list[RecipeSummaryResponse]:
        receitas = await asyncio.to_thread(receitas_repository.listar_receitas, limit)

        return [RecipeSummaryResponse(**receita) for receita in receitas]

    async def sugerir(self, stock_id: int, limit: int) -> list[RecipeSuggestionResponse]:
        sugestoes = await asyncio.to_thread(receitas_repository.match_recipes_to_stock, stock_id, limit)

        return [RecipeSuggestionResponse(**sugestao) for sugestao in sugestoes]


recipe_service = RecipeService()
