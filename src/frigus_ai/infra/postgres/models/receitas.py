from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str | None]
    instructions: Mapped[str | None]
    domestic_only: Mapped[bool]
    active: Mapped[bool]


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "product_id", name="uq_recipe_ingredients_recipe_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None]
    required: Mapped[bool]


class RecipeSuggestion(Base):
    __tablename__ = "recipe_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"))
    matched_ingredients: Mapped[int]
    missing_ingredients: Mapped[int]
    nearest_expire_date: Mapped[date | None]
    score: Mapped[Decimal | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


__all__ = ["Recipe", "RecipeIngredient", "RecipeSuggestion"]
