from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DA_API = ConfigDict(populate_by_name=True, extra="ignore")


class FindRecipesByIngredientsArgs(BaseModel):
    ingredients: list[str] = Field(description="Ingredientes disponíveis (ex.: ['tomate', 'cebola', 'frango']).")
    number: int = Field(default=5, ge=1, le=10, description="Quantidade máxima de receitas retornadas (1-10).")
    ranking: Literal[1, 2] = Field(default=2, description="1 = maximiza ingredientes usados, 2 = minimiza ingredientes faltando (melhor pra 'o que dá pra fazer com o que tenho').")
    ignore_pantry: bool = Field(default=True, description="Ignora itens de despensa (sal, água, azeite etc.) na contagem de faltantes.")


class GetRecipeInformationArgs(BaseModel):
    recipe_id: int = Field(description="ID da receita retornado por find_recipes_by_ingredients ou find_recipes_by_nutrients.")
    include_nutrition: bool = Field(default=False, description="Inclui informação nutricional detalhada (custa ponto de API extra).")


class ReceitaPorIngrediente(BaseModel):
    """Item de `GET /recipes/findByIngredients`."""

    model_config = _DA_API

    id: int
    title: str
    used_count: int = Field(alias="usedIngredientCount")
    missed_count: int = Field(alias="missedIngredientCount")
    missed: list[str] = Field(alias="missedIngredients", default_factory=list)

    @field_validator("missed", mode="before")
    @classmethod
    def _so_os_nomes(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []

        return [
            str(item.get("name", item)) if isinstance(item, Mapping) else str(item)
            for item in v
        ]


class IngredienteReceita(BaseModel):
    """Item de `extendedIngredients` em `GET /recipes/{id}/information`."""

    model_config = _DA_API

    nome: str = Field(alias="name")
    quantidade: float | None = Field(alias="amount", default=None)
    unidade: str | None = Field(alias="unit", default=None)


class ReceitaDetalhada(BaseModel):
    """Resposta de `GET /recipes/{id}/information`."""

    model_config = _DA_API

    id: int
    title: str
    ready_in_minutes: int | None = Field(alias="readyInMinutes", default=None)
    servings: int | None = None
    ingredientes: list[IngredienteReceita] = Field(alias="extendedIngredients", default_factory=list)
    instrucoes: str | None = Field(alias="instructions", default=None)
