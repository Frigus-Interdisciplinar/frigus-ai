from pydantic import BaseModel


class RecipeSummaryResponse(BaseModel):
    recipe_id: int
    name: str
    description: str | None


class RecipeSuggestionResponse(BaseModel):
    recipe_id: int
    name: str
    matched_ingredients: int
    missing_ingredients: int
    nearest_expire_date: str | None
    score: float
