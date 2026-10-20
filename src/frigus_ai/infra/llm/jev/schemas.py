"""
Contrato da Decisions API do Vercel AI Gateway (`POST /v1/decisions`): predicado, escolha e nota.
Cada classe é o JSON do mesmo nome; o mapa completo, com exemplos, está em `.agents/skills/jev.md`.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator


class TipoPergunta(StrEnum):
    PREDICADO = "predicate"
    ESCOLHA   = "choice"
    NOTA      = "score"


class Opcao(BaseModel):
    value:       str
    description: str


class Nivel(BaseModel):
    label:       str
    description: str | None = None


class PerguntaPredicado(BaseModel):
    type:         Literal[TipoPergunta.PREDICADO] = TipoPergunta.PREDICADO
    name:         str
    instructions: str


class PerguntaEscolha(BaseModel):
    type:         Literal[TipoPergunta.ESCOLHA] = TipoPergunta.ESCOLHA
    name:         str
    instructions: str
    choices:      list[Opcao] = Field(min_length=1, max_length=255)

    @field_validator("choices", mode="before")
    @classmethod
    def _de_mapa(cls, choices: Any) -> Any:
        """Aceita `{opção: descrição}`, o formato em que o código já guarda as opções."""

        if isinstance(choices, Mapping):
            return [Opcao(value=str(valor), description=descricao) for valor, descricao in choices.items()]
        return choices


class PerguntaNota(BaseModel):
    type:         Literal[TipoPergunta.NOTA] = TipoPergunta.NOTA
    name:         str
    instructions: str
    levels:       list[Nivel] = Field(min_length=2, max_length=10)


type Pergunta = Annotated[PerguntaPredicado | PerguntaEscolha | PerguntaNota, Field(discriminator="type")]


class PedidoDecisao(BaseModel):
    model:            str
    input:            str
    questions:        list[Pergunta]
    provider_options: dict[str, Any] = Field(serialization_alias="providerOptions")


class Predicado(BaseModel):
    type:        Literal[TipoPergunta.PREDICADO]
    name:        str
    probability: float

    @property
    def sim(self) -> bool:
        return self.probability >= 0.5


class Escolha(BaseModel):
    type:       Literal[TipoPergunta.ESCOLHA]
    name:       str
    choice:     str
    confidence: float | None = None


class Nota(BaseModel):
    type:       Literal[TipoPergunta.NOTA]
    name:       str
    score:      float
    confidence: float | None = None


class Recusa(BaseModel):
    type: Literal["refusal"]
    name: str


type Resposta = Annotated[Predicado | Escolha | Nota | Recusa, Field(discriminator="type")]


class RespostaDecisao(BaseModel):
    model:   str
    answers: list[Resposta]
    usage:   dict[str, int]


__all__ = [
    "Escolha",
    "Nivel",
    "Nota",
    "Opcao",
    "PedidoDecisao",
    "Pergunta",
    "PerguntaEscolha",
    "PerguntaNota",
    "PerguntaPredicado",
    "Predicado",
    "Recusa",
    "Resposta",
    "RespostaDecisao",
    "TipoPergunta",
]
