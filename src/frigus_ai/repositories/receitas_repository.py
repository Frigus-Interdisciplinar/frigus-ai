"""
Persistência crua de receitas: cruza o estoque atual com as receitas cadastradas e
detalha ingredientes. Sem decisão de negócio nem tradução pra `Response` — isso fica
em `graph/tools/receitas/repo.py` (a tool que o LLM chama).
"""

from typing import TypedDict

from sqlalchemy import Float, func, select
from sqlalchemy.orm import Session

from frigus_ai.infra.postgres.connection import PostgresRepo, transacional
from frigus_ai.infra.postgres.helpers import proximo_id
from frigus_ai.infra.postgres.models import (
    Product,
    Recipe,
    RecipeIngredient,
    RecipeSuggestion,
    StockProduct,
)


class RecipeSuggestionInfo(TypedDict):
    recipe_id: int
    name: str
    matched_ingredients: int
    missing_ingredients: int
    nearest_expire_date: str | None
    score: float


class IngredienteInfo(TypedDict):
    product_name: str
    quantity: float | None
    unit: str | None
    required: bool


class RecipeDetails(TypedDict):
    recipe_id: int
    name: str
    description: str | None
    instructions: str | None
    ingredientes: list[IngredienteInfo]


class _ReceitasPostgresRepo(PostgresRepo):
    @transacional
    def match_recipes_to_stock(self, s: Session, stock_id: int, limit: int) -> list[RecipeSuggestionInfo]:
        """
        Cruza o estoque atual (produtos com quantidade > 0) com os ingredientes de
        cada receita ativa e ranqueia por (ingredientes disponíveis / total),
        desempatando pela validade mais próxima. Grava o resultado em
        `recipe_suggestions` (histórico de sugestões).
        """

        estoque_atual = (
            select(
                StockProduct.product_id,
                func.min(StockProduct.expire_date).label("nearest_expire_date"),
            )
            .where(StockProduct.stock_id == stock_id, StockProduct.quantity > 0)
            .group_by(StockProduct.product_id)
            .cte("estoque_atual")
        )

        match = (
            select(
                RecipeIngredient.recipe_id,
                func.count().filter(estoque_atual.c.product_id.isnot(None)).label("matched"),
                func.count().filter(estoque_atual.c.product_id.is_(None)).label("missing"),
                func.min(estoque_atual.c.nearest_expire_date).label("nearest_expire_date"),
            )
            .select_from(RecipeIngredient)
            .outerjoin(estoque_atual, estoque_atual.c.product_id == RecipeIngredient.product_id)
            .group_by(RecipeIngredient.recipe_id)
            .cte("match")
        )

        stmt = (
            select(Recipe.id, Recipe.name, match.c.matched, match.c.missing, match.c.nearest_expire_date)
            .select_from(match)
            .join(Recipe, Recipe.id == match.c.recipe_id)
            .where(Recipe.active.is_(True))
            .order_by(
                (match.c.matched.cast(Float) / func.nullif(match.c.matched + match.c.missing, 0)).desc(),
                match.c.nearest_expire_date.asc().nulls_last(),
            )
            .limit(limit)
        )

        sugestoes: list[RecipeSuggestionInfo] = []
        for recipe_id, name, matched, missing, nearest_expire_date in s.execute(stmt):
            total = matched + missing
            score = round(matched / total, 3) if total else 0.0

            s.add(RecipeSuggestion(
                id=proximo_id(s, RecipeSuggestion),
                recipe_id=recipe_id,
                stock_id=stock_id,
                matched_ingredients=matched,
                missing_ingredients=missing,
                nearest_expire_date=nearest_expire_date,
                score=score,
            ))

            sugestoes.append({
                "recipe_id": recipe_id,
                "name": name,
                "matched_ingredients": matched,
                "missing_ingredients": missing,
                "nearest_expire_date": str(nearest_expire_date) if nearest_expire_date else None,
                "score": score,
            })

        return sugestoes

    @transacional
    def get_recipe_details(self, s: Session, recipe_id: int) -> RecipeDetails | None:
        recipe = s.get(Recipe, recipe_id)
        if recipe is None:
            return None

        stmt = (
            select(Product.name, RecipeIngredient.quantity, RecipeIngredient.unit, RecipeIngredient.required)
            .join(Product, Product.id == RecipeIngredient.product_id)
            .where(RecipeIngredient.recipe_id == recipe_id)
        )

        ingredientes: list[IngredienteInfo] = [
            {
                "product_name": nome,
                "quantity": float(quantidade) if quantidade is not None else None,
                "unit": unidade,
                "required": obrigatorio,
            }
            for nome, quantidade, unidade, obrigatorio in s.execute(stmt)
        ]

        return {
            "recipe_id": recipe.id,
            "name": recipe.name,
            "description": recipe.description,
            "instructions": recipe.instructions,
            "ingredientes": ingredientes,
        }


_receitas = _ReceitasPostgresRepo()


def match_recipes_to_stock(stock_id: int, limit: int) -> list[RecipeSuggestionInfo]:
    return _receitas.match_recipes_to_stock(stock_id, limit)


def get_recipe_details(recipe_id: int) -> RecipeDetails | None:
    return _receitas.get_recipe_details(recipe_id)
