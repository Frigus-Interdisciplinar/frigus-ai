"""
Tipos e política do guardrail: o que o classificador pode devolver e o que fazer com
cada categoria. A *detecção* (regex de PII, jailbreak, keywords) mora em `padroes.py`.
"""

from enum import StrEnum
from typing import Literal, Required, TypedDict

from pydantic import BaseModel


class Categoria(StrEnum):
    """O que o classificador de entrada pode devolver."""

    APROVADO        = "APROVADO"
    OFENSIVO        = "OFENSIVO"
    PERIGOSO        = "PERIGOSO"
    ILICITO         = "ILICITO"
    POLITICO        = "POLITICO"
    CONSELHO_MEDICO = "CONSELHO_MEDICO"


DESCRICAO_CATEGORIA: dict[Categoria, str] = {
    Categoria.APROVADO: (
        "mensagem legítima sobre estoque, compras, receitas ou finanças domésticas, inclusive "
        "informar alergia, intolerância, restrição ou gosto alimentar pra filtrar receitas ou "
        'compras ("tenho alergia a camarão, me sugere uma receita", "sou vegano, o que faço?")'
    ),
    Categoria.OFENSIVO: "xingamentos, assédio, discurso de ódio",
    Categoria.PERIGOSO: "instruções que causam dano físico, psicológico ou coletivo",
    Categoria.ILICITO:  "pedido de auxílio para atividades ilegais ou fraudulentas",
    Categoria.POLITICO: "opiniões ou debates políticos, partidos, eleições",
    Categoria.CONSELHO_MEDICO: (
        "pedido sobre a saúde em si: diagnóstico, tratamento, dieta clínica ou conselho de "
        'saúde/nutrição ("o que tomo pra alergia?", "camarão me deu coceira, é grave?")'
    ),
}


def listar_categorias() -> str:
    """As categorias como texto de prompt, uma por linha: `NOME - descrição`."""

    return "\n".join(f"{categoria} - {descricao}" for categoria, descricao in DESCRICAO_CATEGORIA.items())


class Classificacao(BaseModel):
    """Saída estruturada do classificador de entrada."""

    categoria:     Categoria
    justificativa: str


class RevisaoCompliance(BaseModel):
    """Saída estruturada da revisão de compliance do guardrail de saída."""

    revisada:  str
    modificada: bool


Motivo = Literal[
    "prompt_injection",
    "acesso_dados_internos",
    "conteudo_ofensivo",
    "pedido_perigoso",
    "pedido_ilicito",
    "pergunta_politica",
    "conselho_medico",
    "aprovado",
    "saida_revisada",
]


class RespostaBloqueio(TypedDict):
    """Par motivo/mensagem de uma categoria bloqueada."""

    motivo:   Motivo
    mensagem: str


class ResultadoGuardrail(TypedDict, total=False):
    bloqueado: Required[bool]
    motivo:    Required[Motivo]
    mensagem:  str
    conteudo:  str


RESPOSTAS_BLOQUEIO: dict[Categoria, RespostaBloqueio] = {
    Categoria.OFENSIVO: {
        "motivo":   "conteudo_ofensivo",
        "mensagem": "Por favor, mantenha um tom respeitoso para que eu possa te ajudar.",
    },
    Categoria.PERIGOSO: {
        "motivo":   "pedido_perigoso",
        "mensagem": "Não posso ajudar com esse tipo de solicitação.",
    },
    Categoria.ILICITO: {
        "motivo":   "pedido_ilicito",
        "mensagem": "Não posso auxiliar com atividades ilegais ou irregulares.",
    },
    Categoria.POLITICO: {
        "motivo":   "pergunta_politica",
        "mensagem": (
            "Não me envolvo em temas políticos. Posso ajudar com seu estoque, compras, "
            "receitas ou finanças domésticas."
        ),
    },
    Categoria.CONSELHO_MEDICO: {
        "motivo":   "conselho_medico",
        "mensagem": (
            "Não posso dar conselhos de saúde, nutrição clínica ou diagnóstico — procure "
            "um profissional. Posso ajudar com estoque, compras ou receitas."
        ),
    },
}


__all__ = [
    "DESCRICAO_CATEGORIA",
    "RESPOSTAS_BLOQUEIO",
    "Categoria",
    "Classificacao",
    "Motivo",
    "RespostaBloqueio",
    "ResultadoGuardrail",
    "RevisaoCompliance",
    "listar_categorias",
]
