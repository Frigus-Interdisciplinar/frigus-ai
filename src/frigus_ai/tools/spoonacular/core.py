import time
from functools import lru_cache

import httpx
from langchain.tools import tool

from config.decorators import log_tool
from config.logging import get_logger
from config.settings import settings
from frigus_ai.tools.response import Response

from .connection import cliente
from .schemas import (
    FindRecipesByIngredientsArgs,
    GetRecipeInformationArgs,
    ReceitaDetalhada,
    ReceitaPorIngrediente,
)

logger = get_logger("spoonacular")

# ToS da Spoonacular: cache de resposta no máximo 1h. A janela entra na chave do
# lru_cache, então a entrada velha vira lixo sozinha na virada da hora.
_TTL_SEGUNDOS = 3600


@lru_cache(maxsize=128)
def _get(path: str, params: tuple[tuple[str, object], ...], _janela: int):
    
    resposta = cliente.get(path, params=dict(params), timeout=10)
    resposta.raise_for_status()

    return resposta.json()


def _chamar(path: str, params: dict):
    if not settings.SPOONACULAR_API_KEY:
        raise RuntimeError("SPOONACULAR_API_KEY não configurada")

    chave = tuple(sorted((k, v) for k, v in params.items() if v is not None))
    
    try:
        return _get(path, chave, int(time.time()) // _TTL_SEGUNDOS)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 402:
            raise RuntimeError(
                "cota diária da API de receitas (Spoonacular) esgotada — tente novamente amanhã"
            ) from e
        raise


@tool("find_recipes_by_ingredients", args_schema=FindRecipesByIngredientsArgs)
@log_tool
def find_recipes_by_ingredients(
    ingredients: list[str],
    number: int = 10,
    ranking: int = 2,
    ignore_pantry: bool = True,
) -> dict:
    """
    Busca receitas externas (Spoonacular) que aproveitam ao máximo os ingredientes
    informados — tipicamente o que o usuário tem no estoque. Cada receita vem com a
    contagem de ingredientes usados e faltando, e o nome dos que faltam.
    """

    try:
        dados = _chamar(
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
            for r in dados
        ]

        return Response.ok(
            total=len(receitas), 
            receitas=receitas
        )

    except Exception as e:
        logger.error("ERRO | find_recipes_by_ingredients | %s", e)
        return Response.error(e)


@tool("get_recipe_information", args_schema=GetRecipeInformationArgs)
@log_tool
def get_recipe_information(recipe_id: int, include_nutrition: bool = False) -> dict:
    """
    Detalha uma receita externa (Spoonacular): ingredientes com quantidade e
    unidade, tempo de preparo, porções e modo de preparo.
    """

    try:
        dados = _chamar(
            f"/recipes/{recipe_id}/information",
            {"includeNutrition": include_nutrition},
        )

        return Response.ok(
            **ReceitaDetalhada.model_validate(dados).model_dump()
        )

    except Exception as e:
        logger.error("ERRO | get_recipe_information | %s", e)
        return Response.error(e)


__all__ = ["find_recipes_by_ingredients", "get_recipe_information"]
