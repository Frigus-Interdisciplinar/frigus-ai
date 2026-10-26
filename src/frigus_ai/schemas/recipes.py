from typing import Literal

from pydantic import BaseModel, Field


class RecipeSummaryResponse(BaseModel):
    recipe_id: int
    source: Literal["local", "spoonacular"] = "local"
    name: str
    description: str | None = None
    image_url: str | None = None
    ready_in_minutes: int | None = Field(default=None, ge=0)
    servings: int | None = Field(default=None, gt=0)
    is_favorite: bool = False


class RecipeSuggestionResponse(RecipeSummaryResponse):
    matched_ingredients: int
    missing_ingredients: int
    nearest_expire_date: str | None
    score: float
    expiring_ingredients: list[str] = Field(default_factory=list)
    matched_ingredient_names: list[str] = Field(default_factory=list)
    missing_ingredient_names: list[str] = Field(default_factory=list)
    reason: str | None = None
    unverified_restrictions: list[str] = Field(default_factory=list)


class RecipeIngredientResponse(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None


class NutrientResponse(BaseModel):
    name: str
    amount: float
    unit: str


class RecipeDetailResponse(RecipeSummaryResponse):
    ingredients: list[RecipeIngredientResponse] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    source_name: str | None = None
    source_url: str | None = None
    credits_text: str | None = None
    nutrients: list[NutrientResponse] | None = None
