from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.receitas.schemas import (
    GetRecipeDetailsArgs,
    MatchRecipesToStockArgs,
)
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.postgres.context import current_stock_id
from frigus_ai.logging import Logging
from frigus_ai.repositories import receitas_repository

logger = Logging.get_logger("pg_receitas")


class ReceitasRepo(ToolSet):
    @Logging.log_tool
    def match_recipes_to_stock(self, limit: int = 5) -> dict:
        """
        Cruza as receitas cadastradas com o estoque atual do usuário e retorna as
        mais viáveis, priorizando quem usa ingredientes próximos do vencimento.

        Grava o resultado em recipe_suggestions (histórico de sugestões) e retorna
        a lista ranqueada por (ingredientes disponíveis / total) e proximidade de vencimento.
        """

        try:
            sugestoes = receitas_repository.match_recipes_to_stock(current_stock_id(), limit)
        except Exception as e:
            logger.error("MATCH ERRO | match_recipes_to_stock | %s", e)
            return Response.error(e)

        logger.info("MATCH OK | match_recipes_to_stock | total=%s", len(sugestoes))
        return Response.ok(total_records=len(sugestoes), sugestoes=sugestoes)

    @Logging.log_tool
    def get_recipe_details(self, recipe_id: int) -> dict:
        """
        Retorna o modo de preparo e a lista de ingredientes de uma receita específica.
        """

        try:
            detalhes = receitas_repository.get_recipe_details(recipe_id)
        except Exception as e:
            logger.error("QUERY ERRO | get_recipe_details | %s", e)
            return Response.error(e)

        if detalhes is None:
            return Response.error(f"Receita {recipe_id} não encontrada.")

        logger.info("QUERY OK | get_recipe_details | recipe_id=%s", recipe_id)
        return Response.ok(**detalhes)

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                self.match_recipes_to_stock,
                name="match_recipes_to_stock",
                args_schema=MatchRecipesToStockArgs,
            ),
            StructuredTool.from_function(
                self.get_recipe_details, name="get_recipe_details", args_schema=GetRecipeDetailsArgs
            ),
        ]


__all__ = ["ReceitasRepo"]
