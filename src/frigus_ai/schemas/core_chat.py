from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FoodPreference = Literal[
    "VEGETARIAN", "VEGAN", "NO_RED_MEAT", "NO_SEAFOOD", "NO_LACTOSE",
    "NO_GLUTEN", "NO_SUGAR", "QUICK_RECIPES", "ECONOMICAL_RECIPES",
]


class CoreChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    userId: UUID
    stockId: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=4000)
    sessionId: str | None = Field(default=None, min_length=1, max_length=200)
    foodPreferences: list[FoodPreference] = Field(default_factory=list, max_length=9)


class CoreChatResponse(BaseModel):
    sessionId: str
    chatMessage: str
    recipeIds: list[int]
