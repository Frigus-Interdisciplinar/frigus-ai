import asyncio
import inspect
import time
from typing import NamedTuple, cast

import httpx
from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.exceptions import ApiKeyNaoConfiguradaError, CotaExcedidaError
from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.response import Response, ToolResponse
from frigus_ai.infra.spoonacular.connection import spoonacular
from frigus_ai.settings import settings

from .schemas import (
    FindRecipesByIngredientsArgs,
    GetRecipeInformationArgs,
    ReceitaDetalhada,
    ReceitaPorIngrediente,
)

_TTL_SEGUNDOS = 3600
_MAX_CACHE_ENTRIES = 128

type _Path = str
type _ParamValue = str | int | float | bool | None


class _Param(NamedTuple):
    nome: str
    valor: _ParamValue


type _Params = tuple[_Param, ...]


class _ChaveCache(NamedTuple):
    path: _Path
    params: _Params
    janela: int


class _CachedGet:
    def __init__(self) -> None:
        self._cache: dict[_ChaveCache, object] = {}

    async def __call__(self, path: _Path, params: _Params, janela: int) -> object:
        chave = _ChaveCache(path, params, janela)
        if chave in self._cache:
            return self._cache[chave]

        resposta = spoonacular.connect().get(path, params=dict(params), timeout=10)
        if inspect.isawaitable(resposta):
            resposta = await resposta

        resposta_http = cast(httpx.Response, resposta)
        resposta_http.raise_for_status()

        if len(self._cache) >= _MAX_CACHE_ENTRIES:
            self._cache.pop(next(iter(self._cache)))
        self._cache[chave] = resposta_http.json()

        return self._cache[chave]

    def cache_clear(self) -> None:
        self._cache.clear()


_get = _CachedGet()


async def _chamar(path: _Path, params: dict[str, _ParamValue]) -> object:
    if not settings.SPOONACULAR_API_KEY:
        raise ApiKeyNaoConfiguradaError

    chave: _Params = tuple(_Param(nome, valor) for nome, valor in sorted(params.items()))

    try:
        return await _get(path, chave, int(time.time()) // _TTL_SEGUNDOS)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 402:
            raise CotaExcedidaError from e
        raise


class SpoonacularRepo(ToolSet):
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
            ReceitaPorIngrediente.model_validate(r).model_dump() for r in cast(list[object], dados)
        ]

        return Response.ok(total=len(receitas), receitas=receitas)

    async def get_recipe_information(
        self,
        recipe_id: int,
        include_nutrition: bool = False,
    ) -> ToolResponse:
        """
        Detalha uma receita externa (Spoonacular): ingredientes com quantidade e
        unidade, tempo de preparo, porções e modo de preparo.
        """

        dados = await _chamar(
            f"/recipes/{recipe_id}/information",
            {"includeNutrition": include_nutrition},
        )

        return Response.ok(**ReceitaDetalhada.model_validate(dados).model_dump())

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
