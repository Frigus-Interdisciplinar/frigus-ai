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

    # Opções que só existem em runtime (ids, nomes de produto): a métrica não pode usá-las como rótulo.
    dinamica:     bool = Field(default=False, exclude=True)

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


class ParteTexto(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str


class ParteImagem(BaseModel):
    """O gateway só aceita data URL em base64 (nada de URL externa nem file_id), até 128 por pedido."""

    type:      Literal["input_image"] = "input_image"
    image_url: str


class MensagemUsuario(BaseModel):
    role:    Literal["user"] = "user"
    content: list[ParteTexto | ParteImagem]


class PedidoDecisao(BaseModel):
    model:            str
    input:            str | list[MensagemUsuario]
    questions:        list[Pergunta]
    provider_options: dict[str, Any] | None = Field(default=None, serialization_alias="providerOptions")


class Predicado(BaseModel):
    type:        Literal[TipoPergunta.PREDICADO]
    name:        str
    probability: float

    @property
    def sim(self) -> bool:
        return self.probability >= 0.5


class ProbabilidadeOpcao(BaseModel):
    value:       str
    probability: float


class Escolha(BaseModel):
    type:          Literal[TipoPergunta.ESCOLHA]
    name:          str
    choice:        str
    confidence:    float | None = None
    probabilities: list[ProbabilidadeOpcao] = []


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
    model:             str
    answers:           list[Resposta]
    usage:             dict[str, int]
    provider_metadata: dict[str, Any] = {}


__all__ = [
    "Escolha",
    "MensagemUsuario",
    "Nivel",
    "Nota",
    "Opcao",
    "ParteImagem",
    "ParteTexto",
    "PedidoDecisao",
    "Pergunta",
    "PerguntaEscolha",
    "PerguntaNota",
    "PerguntaPredicado",
    "Predicado",
    "ProbabilidadeOpcao",
    "Recusa",
    "Resposta",
    "RespostaDecisao",
    "TipoPergunta",
]
