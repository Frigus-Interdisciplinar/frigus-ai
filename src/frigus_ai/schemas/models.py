"""Tipos de domínio compartilhados entre services e schemas de API."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, field_validator


class Role(StrEnum):
    HUMAN = "human"
    AI = "ai"


@dataclass
class ChatMessage:
    role: Role
    content: str


RESTRICOES_CANONICAS = [
    "Vegetariano",
    "Vegano",
    "Sem lactose",
    "Sem glúten",
    "Kosher",
    "Halal",
    "Low carb",
    "Sem açúcar",
    "Sem frutos do mar",
    "Sem carne vermelha",
]


def _sem_acento(texto: str) -> str:
    troca = str.maketrans("áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ", "aaaaeeiooouucAAAAEEIOOOUUC")
    return texto.translate(troca).strip().lower()


def _normalizar_restricao(valor: str) -> str:
    """
    Resolve `valor` (texto livre vindo do LLM ou de `PUT /profile`) pro valor exato
    de `RESTRICOES_CANONICAS`, comparando sem acento/case. Sem correspondência,
    devolve o valor cru (só com espaços nas pontas removidos) — restrição alimentar é
    informação de segurança/preferência real do usuário, nunca pode ser descartada só
    por grafia não reconhecida (mesma regra do `normalize_enum` de
    `graph/tools/estoque/helpers.py`, mas sem o `None` no caso de falha).
    """

    alvo = _sem_acento(valor)
    for opcao in RESTRICOES_CANONICAS:
        if _sem_acento(opcao) == alvo:
            return opcao
    return valor.strip()


class Fatos(BaseModel):
    """
    Fatos estruturados extraídos da conversa (coleção `user_fatos` no Mongo). Mesma
    forma nos três usos: saída do LLM de extração (`with_structured_output`,
    `services/chat_service.py`), schema de `/v1/profile` e retorno de
    `repositories/fatos_repository.py` — por isso mora aqui, não num `schemas/`
    específico de API nem dentro do repository.
    """

    alergias:     list[str] = []
    preferencias: list[str] = []
    restricoes:   list[str] = []
    habitos:      list[str] = []

    @field_validator("restricoes")
    @classmethod
    def _normalizar_restricoes(cls, valores: list[str]) -> list[str]:
        """Roda em toda construção de `Fatos` (extração, merge, PUT manual) — não só
        normaliza a grafia, também dedupe (`"vegetariano"` e `"Vegetariano"` colapsam
        no mesmo valor canônico)."""

        vistos: dict[str, None] = {}
        for valor in valores:
            vistos.setdefault(_normalizar_restricao(valor), None)
        return list(vistos)
