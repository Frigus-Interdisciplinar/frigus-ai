from langchain.tools import tool

from config.decorators import log_tool
from config.logging import get_logger
from frigus_ai.tools.postgres.connection import get_conn
from frigus_ai.tools.postgres.context import current_stock_id
from frigus_ai.tools.postgres.helpers import next_id
from frigus_ai.tools.postgres.receitas.schemas import (
    GetRecipeDetailsArgs,
    MatchRecipesToStockArgs,
)
from frigus_ai.tools.response import Response

logger = get_logger("pg_receitas")


@tool("match_recipes_to_stock", args_schema=MatchRecipesToStockArgs)
@log_tool
def match_recipes_to_stock(limit: int = 5) -> dict:
    """
    Cruza as receitas cadastradas com o estoque atual do usuário e retorna as
    mais viáveis, priorizando quem usa ingredientes próximos do vencimento.

    Grava o resultado em recipe_suggestions (histórico de sugestões) e retorna
    a lista ranqueada por (ingredientes disponíveis / total) e proximidade de vencimento.
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    WITH stock_atual AS (
                        SELECT product_id, MIN(expire_date) AS nearest_expire_date
                        FROM stock_products
                        WHERE stock_id = %s AND quantity > 0
                        GROUP BY product_id
                    ),
                    match AS (
                        SELECT
                            ri.recipe_id,
                            COUNT(*) FILTER (WHERE sa.product_id IS NOT NULL) AS matched,
                            COUNT(*) FILTER (WHERE sa.product_id IS NULL) AS missing,
                            MIN(sa.nearest_expire_date) AS nearest_expire_date
                        FROM recipe_ingredients ri
                        LEFT JOIN stock_atual sa ON sa.product_id = ri.product_id
                        GROUP BY ri.recipe_id
                    )
                    SELECT r.id, r.name, m.matched, m.missing, m.nearest_expire_date
                    FROM match m
                    JOIN recipes r ON r.id = m.recipe_id
                    WHERE r.active = TRUE
                    ORDER BY
                        (m.matched::float / NULLIF(m.matched + m.missing, 0)) DESC,
                        m.nearest_expire_date ASC NULLS LAST
                    LIMIT %s;
                    """,
                    (stock_id, limit)
                )
                rows = cur.fetchall()

                sugestoes = []
                for recipe_id, name, matched, missing, nearest_expire_date in rows:
                    total = matched + missing
                    score = round(matched / total, 3) if total else 0.0

                    suggestion_id = next_id(cur, "recipe_suggestions")
                    cur.execute(
                        """
                        INSERT INTO recipe_suggestions
                            (id, recipe_id, stock_id, matched_ingredients, missing_ingredients, nearest_expire_date, score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """,
                        (suggestion_id, recipe_id, stock_id, matched, missing, nearest_expire_date, score)
                    )

                    sugestoes.append({
                        "recipe_id": recipe_id,
                        "name": name,
                        "matched_ingredients": matched,
                        "missing_ingredients": missing,
                        "nearest_expire_date": str(nearest_expire_date) if nearest_expire_date else None,
                        "score": score,
                    })

                conn.commit()

                logger.info("MATCH OK | match_recipes_to_stock | total=%s", len(sugestoes))

                return Response.ok(total_records=len(sugestoes), sugestoes=sugestoes)

            except Exception as e:
                conn.rollback()
                logger.error("MATCH ERRO | match_recipes_to_stock | %s", e)
                return Response.error(e)


@tool("get_recipe_details", args_schema=GetRecipeDetailsArgs)
@log_tool
def get_recipe_details(recipe_id: int) -> dict:
    """
    Retorna o modo de preparo e a lista de ingredientes de uma receita específica.
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "SELECT id, name, description, instructions FROM recipes WHERE id = %s;",
                    (recipe_id,)
                )
                row = cur.fetchone()
                if not row:
                    return Response.error(f"Receita {recipe_id} não encontrada.")

                cur.execute(
                    """
                    SELECT p.name, ri.quantity, ri.unit, ri.required
                    FROM recipe_ingredients ri
                    JOIN products p ON p.id = ri.product_id
                    WHERE ri.recipe_id = %s;
                    """,
                    (recipe_id,)
                )
                ingredientes = [
                    {
                        "product_name": r[0],
                        "quantity": float(r[1]) if r[1] is not None else None,
                        "unit": r[2],
                        "required": r[3],
                    }
                    for r in cur.fetchall()
                ]

                logger.info("QUERY OK | get_recipe_details | recipe_id=%s", recipe_id)

                return Response.ok(
                    recipe_id=row[0],
                    name=row[1],
                    description=row[2],
                    instructions=row[3],
                    ingredientes=ingredientes,
                )

            except Exception as e:
                logger.error("QUERY ERRO | get_recipe_details | %s", e)
                return Response.error(e)


__all__ = ["get_recipe_details", "match_recipes_to_stock"]
