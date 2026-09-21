"""
Anonimização de PII — módulo neutro, sem dependência de nenhuma camada.

Vive aqui, e não em `graph/nodes/guardrail/`, porque tem consumidores em três camadas
diferentes: o guardrail (entrada e saída), a persistência de mensagens em
`repositories/chat_repository.py` e a redação de perfil em `services/user_service.py`.
Enquanto morava dentro do guardrail, repository e service importavam de `graph/nodes/` —
inversão de dependência (a persistência não deveria saber que existe um grafo).

O que é *detecção de ataque* (jailbreak, pedido de dado interno) continua em
`graph/nodes/guardrail/padroes.py`: aquilo só o guardrail usa.
"""

import re
import uuid
from typing import NamedTuple

type MapaPII = dict[str, str]


class PIIPattern(NamedTuple):
    tipo: str
    padrao: str
    redige_na_saida: bool = True  # False = contato: só a entrada anonimiza, a saída não redige


# Fonte única — `redige_na_saida=False` marca contato (email/telefone). `PII_USUARIO` deriva
# daqui por filtro, sem lista duplicada.
PII: list[PIIPattern] = [
    PIIPattern("CPF",       r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"),
    PIIPattern("CNPJ",      r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"),
    PIIPattern("SENHA",     r"(?i)senha[:\s]+\S+"),
    PIIPattern("EMAIL",     r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", redige_na_saida=False),
    PIIPattern("TELEFONE",  r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}",                   redige_na_saida=False),
]

# PII do usuário — redigida na entrada E na saída.
PII_USUARIO: list[PIIPattern] = [p for p in PII if p.redige_na_saida]


def anonimizar_entrada(texto: str) -> tuple[str, MapaPII]:
    """Troca cada PII por um token único e devolve o texto limpo + o mapa pra reverter."""

    mapa: MapaPII = {}

    for pii in PII:
        for valor in re.findall(pii.padrao, texto):
            token = f"[PII_{pii.tipo}_{uuid.uuid4().hex[:6]}]"
            mapa[token] = valor
            texto = texto.replace(valor, token, 1)

    return texto, mapa


def desanonimizar_saida(texto: str, mapa: MapaPII, restaurar: bool = False) -> str:
    """Por padrão omite o valor original, não repete dado pessoal na saída."""

    for token, valor in mapa.items():
        if token not in texto:
            continue

        substituto = valor if restaurar else f"[{token.split('_')[1]} OMITIDO]"
        texto = texto.replace(token, substituto)

    return texto


def redigir_pii(texto: str, padroes: list[PIIPattern] | None = None) -> str:
    """Apaga PII que o modelo tenha gerado por conta própria (não veio do mapa da entrada)."""

    for pii in padroes if padroes is not None else PII:
        texto = re.sub(pii.padrao, f"[{pii.tipo} OMITIDO]", texto)

    return texto


__all__ = [
    "PII",
    "PII_USUARIO",
    "MapaPII",
    "PIIPattern",
    "anonimizar_entrada",
    "desanonimizar_saida",
    "redigir_pii",
]
