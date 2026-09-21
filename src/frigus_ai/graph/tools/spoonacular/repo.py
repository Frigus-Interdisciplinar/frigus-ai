import asyncio
import inspect
import time
from typing import cast

import httpx
from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.exceptions import ApiKeyNaoConfiguradaError, CotaExcedidaError
from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.response import Response, ToolResponse
from frigus_ai.logging import Logging
from frigus_ai.settings import settings

from .connection import spoonacular
from .schemas import (
    FindRecipesByIngredientsArgs,
    GetRecipeInformationArgs,
    ReceitaDetalhada,
    ReceitaPorIngrediente,
)

logger = Logging.get_logger("spoonacular")

_TTL_SEGUNDOS = 3600
_ParamValue = str | int | float | bool | None


class _CachedGet:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[tuple[str, _ParamValue], ...], int], object] = {}

    async def __call__(
        self,
        path: str,
        params: tuple[tuple[str, _ParamValue], ...],
        janela: int,
    ) -> object:
        chave = (path, params, janela)
        if chave in self._cache:
            return self._cache[chave]

        resposta: object = spoonacular.connect().get(path, params=dict(params), timeout=10)
        if inspect.isawaitable(resposta):
            resposta = await resposta

        resposta_http = cast(httpx.Response, resposta)
        resposta_http.raise_for_status()
        dados = resposta_http.json()

        if len(self._cache) >= 128:
            self._cache.pop(next(iter(self._cache)))
        self._cache[chave] = dados
        return dados

    def cache_clear(self) -> None:
        self._cache.clear()


_get = _CachedGet()


async def _chamar(path: str, params: dict[str, _ParamValue]) -> object:
    if not settings.SPOONACULAR_API_KEY:
        raise ApiKeyNaoConfiguradaError

    chave = tuple(sorted(params.items()))

    try:
        return await _get(path, chave, int(time.time()) // _TTL_SEGUNDOS)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 402:
            raise CotaExcedidaError from e
        raise


class SpoonacularRepo(ToolSet):
    @Logging.log_tool
    async def find_recipes_by_ingredients(
        self,
        ingredients: list[str],
        number: int = 10,
        ranking: int = 2,
        ignore_pantry: bool = True,
    ) -> ToolResponse:
        """
        Busca receitas externas (Spoonacular) que aproveitam ao máximo os ingredientes
        informados — tipicamente o que o usuário tem no estoque. Cada receita vem com a
        contagem de ingredientes usados e faltando, e o nome dos que faltam.
        """

        try:
            dados = await _chamar(
                "/recipes/findByIngredients",
                {
                    "ingredients": ",".join(ingredients),
                    "number": number,
                    "ranking": ranking,
                    "ignorePantry": ignore_pantry,
                },
            )

            receitas = [
                ReceitaPorIngrediente.model_validate(r).model_dump()
                for r in cast(list[object], dados)
            ]

            return Response.ok(total=len(receitas), receitas=receitas)

        except Exception as e:
            logger.error("ERRO | find_recipes_by_ingredients | %s", e)
            return Response.error(e)

    @Logging.log_tool
    async def get_recipe_information(
        self,
        recipe_id: int,
        include_nutrition: bool = False,
    ) -> ToolResponse:
        """
        Detalha uma receita externa (Spoonacular): ingredientes com quantidade e
        unidade, tempo de preparo, porções e modo de preparo.
        """

        try:
            dados = await _chamar(
                f"/recipes/{recipe_id}/information",
                {"includeNutrition": include_nutrition},
            )

            return Response.ok(**ReceitaDetalhada.model_validate(dados).model_dump())

        except Exception as e:
            logger.error("ERRO | get_recipe_information | %s", e)
            return Response.error(e)

    def as_tools(self) -> list[BaseTool]:
        def find_sync(**kwargs):
            """Executa a busca de receitas para callers síncronos legados."""
            return asyncio.run(self.find_recipes_by_ingredients(**kwargs))

        def information_sync(**kwargs):
            """Executa o detalhamento de receita para callers síncronos legados."""
            return asyncio.run(self.get_recipe_information(**kwargs))

        return [
            StructuredTool.from_function(
                find_sync,
                coroutine=self.find_recipes_by_ingredients,
                name="find_recipes_by_ingredients",
                description=self.find_recipes_by_ingredients.__doc__,
                args_schema=FindRecipesByIngredientsArgs,
            ),
            StructuredTool.from_function(
                information_sync,
                coroutine=self.get_recipe_information,
                name="get_recipe_information",
                description=self.get_recipe_information.__doc__,
                args_schema=GetRecipeInformationArgs,
            ),
        ]


__all__ = ["SpoonacularRepo"]
