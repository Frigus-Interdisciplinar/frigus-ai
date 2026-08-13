from pydantic import BaseModel, Field


class MatchRecipesToStockArgs(BaseModel):
    limit: int = Field(default=5, description="Número máximo de receitas a sugerir.")


class GetRecipeDetailsArgs(BaseModel):
    recipe_id: int = Field(..., description="ID da receita retornado por match_recipes_to_stock.")
