from pydantic import BaseModel, Field


class MatchRecipesToStockArgs(BaseModel):
    limit: int = Field(default=5, description="Número máximo de receitas a sugerir.")


class GetRecipeDetailsArgs(BaseModel):
    recipe_id: int = Field(description="ID da receita retornado por match_recipes_to_stock.")


class SalvarSugestoesArgs(BaseModel):
    recipe_ids: list[int] = Field(min_length=1, max_length=10, description="IDs das receitas do catálogo efetivamente recomendadas neste turno.")
