from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DA_API = ConfigDict(populate_by_name=True, extra="ignore")


class FindRecipesByIngredientsArgs(BaseModel):
    ingredients: list[str] = Field(description="Ingredientes disponíveis (ex.: ['tomate', 'cebola', 'frango']).")
    number: int = Field(default=5, ge=1, le=10, description="Quantidade máxima de receitas retornadas (1-10).")
    # `int` com limites, não `Literal[1, 2]`: o Gemini rejeita `enum` de inteiros no schema da tool
    # (pydantic ValidationError em `Schema.enum`) e o especialista inteiro vira 500.
    ranking: int = Field(default=2, ge=1, le=2, description="1 = maximiza ingredientes usados, 2 = minimiza ingredientes faltando (melhor pra 'o que dá pra fazer com o que tenho').")
    ignore_pantry: bool = Field(default=True, description="Ignora itens de despensa (sal, água, azeite etc.) na contagem de faltantes.")


class GetRecipeInformationArgs(BaseModel):
    recipe_id: int = Field(description="ID da receita retornado por find_recipes_by_ingredients ou find_recipes_by_nutrients.")
    include_nutrition: bool = Field(default=False, description="Inclui informação nutricional detalhada (custa ponto de API extra).")


class ReceitaPorIngrediente(BaseModel):
    """Item de `GET /recipes/findByIngredients`."""

    model_config = _DA_API

    id: int
    title: str
    image_url: str | None = Field(alias="image", default=None)
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


class EtapaReceita(BaseModel):
    number: int
    step: str


class GrupoPreparo(BaseModel):
    name: str = ""
    steps: list[EtapaReceita] = Field(default_factory=list)


class Nutriente(BaseModel):
    name: str
    amount: float
    unit: str


class Nutricao(BaseModel):
    """Valores por porção."""

    nutrients: list[Nutriente] = Field(default_factory=list)


class ReceitaDetalhada(BaseModel):
    """Resposta de `GET /recipes/{id}/information`."""

    model_config = _DA_API

    id: int
    title: str
    image_url: str | None = Field(alias="image", default=None)
    ready_in_minutes: int | None = Field(alias="readyInMinutes", default=None)
    servings: int | None = None
    ingredientes: list[IngredienteReceita] = Field(alias="extendedIngredients", default_factory=list)
    instrucoes: str | None = Field(alias="instructions", default=None)
    preparo: list[GrupoPreparo] = Field(alias="analyzedInstructions", default_factory=list)
    nutrition: Nutricao | None = None
    source_name: str | None = Field(alias="sourceName", default=None)
    source_url: str | None = Field(alias="sourceUrl", default=None)
    credits_text: str | None = Field(alias="creditsText", default=None)
    license: str | None = None
