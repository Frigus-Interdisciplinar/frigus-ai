from typing import Literal

from pydantic import BaseModel, Field


class SearchIngredientsArgs(BaseModel):
    query: str = Field(description="Termo de busca do ingrediente (ex.: 'tomate', 'peito de frango').")
    number: int = Field(default=10, description="Quantidade máxima de resultados (1-100).")
    intolerances: str | None = Field(default=None, description="Filtro por intolerância alimentar (ex.: 'gluten,dairy').")


class GetIngredientInformationArgs(BaseModel):
    ingredient_id: int = Field(description="ID do ingrediente retornado por search_ingredients.")
    amount: float = Field(default=1, description="Quantidade do ingrediente, usada pra calcular a nutrição proporcional.")
    unit: str | None = Field(default=None, description="Unidade da quantidade acima (ex.: 'g', 'cups'). Se ausente, usa a unidade padrão do ingrediente.")


class FindRecipesByIngredientsArgs(BaseModel):
    ingredients: list[str] = Field(description="Ingredientes disponíveis (ex.: ['tomate', 'cebola', 'frango']).")
    number: int = Field(default=10, description="Quantidade máxima de receitas retornadas (1-100).")
    ranking: Literal[1, 2] = Field(default=2, description="1 = maximiza ingredientes usados, 2 = minimiza ingredientes faltando (melhor pra 'o que dá pra fazer com o que tenho').")
    ignore_pantry: bool = Field(default=True, description="Ignora itens de despensa (sal, água, azeite etc.) na contagem de faltantes.")


class FindRecipesByNutrientsArgs(BaseModel):
    min_calories: float | None = Field(default=None, description="Calorias mínimas por porção.")
    max_calories: float | None = Field(default=None, description="Calorias máximas por porção.")
    min_protein: float | None = Field(default=None, description="Proteína mínima (g) por porção.")
    max_protein: float | None = Field(default=None, description="Proteína máxima (g) por porção.")
    min_fat: float | None = Field(default=None, description="Gordura mínima (g) por porção.")
    max_fat: float | None = Field(default=None, description="Gordura máxima (g) por porção.")
    min_carbs: float | None = Field(default=None, description="Carboidrato mínimo (g) por porção.")
    max_carbs: float | None = Field(default=None, description="Carboidrato máximo (g) por porção.")
    number: int = Field(default=10, description="Quantidade máxima de receitas retornadas (1-100).")


class GetRecipeInformationArgs(BaseModel):
    recipe_id: int = Field(description="ID da receita retornado por find_recipes_by_ingredients ou find_recipes_by_nutrients.")
    include_nutrition: bool = Field(default=False, description="Inclui informação nutricional detalhada (custa ponto de API extra).")


class GetSimilarRecipesArgs(BaseModel):
    recipe_id: int = Field(description="ID da receita de referência.")
    number: int = Field(default=5, description="Quantidade máxima de receitas similares (1-100).")
