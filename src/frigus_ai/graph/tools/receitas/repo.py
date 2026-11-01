from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.domain.recipe_turn import turno_atual
from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.receitas.schemas import (
    GetRecipeDetailsArgs,
    MatchRecipesToStockArgs,
    SalvarSugestoesArgs,
)
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.postgres.context import current_stock_id
from frigus_ai.repositories import receitas_repository


class ReceitasRepo(ToolSet):
    def match_recipes_to_stock(self, limit: int = 5) -> dict:
        """
        Cruza as receitas cadastradas com o estoque atual do usuário e retorna as
        mais viáveis, priorizando quem usa ingredientes próximos do vencimento.

        Grava o resultado em recipe_suggestions (histórico de sugestões) e retorna
        a lista ranqueada por (ingredientes disponíveis / total) e proximidade de vencimento.
        """

        turno = turno_atual()
        filtros = {}
        if turno is not None:
            categorias, termos = turno.exclusoes()
            filtros = {"categorias_excluidas": categorias, "termos_excluidos": termos, "persistir": False}
        sugestoes = receitas_repository.match_recipes_to_stock(current_stock_id(), min(max(limit, 1), 10), **filtros)
        if turno is not None:
            turno.candidates.update({s["recipe_id"]: s["name"] for s in sugestoes})
        return Response.ok(total_records=len(sugestoes), sugestoes=sugestoes)

    def salvar_sugestoes_receitas(self, recipe_ids: list[int]) -> dict:
        """Registra somente as receitas do catálogo que você efetivamente recomenda, depois de aplicar as preferências e alergias do usuário."""

        turno = turno_atual()
        if turno is None:
            return Response.error("O registro explícito de sugestões requer a integração com o aplicativo Frigus.")
        if not recipe_ids or len(recipe_ids) > 10 or any(i not in turno.candidates for i in recipe_ids):
            return Response.error("Selecione apenas IDs retornados por match_recipes_to_stock neste turno.")
        turno.recipes.update({i: turno.candidates[i] for i in recipe_ids})
        return Response.ok(recipe_ids=list(turno.recipes))

    def get_recipe_details(self, recipe_id: int) -> dict:
        """
        Retorna o modo de preparo e a lista de ingredientes de uma receita específica.
        """

        detalhes = receitas_repository.get_recipe_details(recipe_id)
        if detalhes is None:
            return Response.error(f"Receita {recipe_id} não encontrada.")

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
            StructuredTool.from_function(
                self.salvar_sugestoes_receitas, name="salvar_sugestoes_receitas", args_schema=SalvarSugestoesArgs,
            ),
        ]


__all__ = ["ReceitasRepo"]
