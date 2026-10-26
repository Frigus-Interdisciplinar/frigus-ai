"""
Anonimização de PII — módulo neutro, sem dependência de nenhuma camada.

Vive aqui, e não em `graph/nodes/guardrail/`, porque tem consumidores em duas camadas
diferentes: o guardrail (entrada e saída) e a persistência de mensagens em
`repositories/chat_repository.py`. Enquanto morava dentro do guardrail, o repository
importava de `graph/nodes/` — inversão de dependência (a persistência não deveria
saber que existe um grafo).

O que é *detecção de ataque* (jailbreak, pedido de dado interno) continua em
`graph/nodes/guardrail/padroes.py`: aquilo só o guardrail usa.
"""

import re
import uuid
from collections.abc import Callable
from typing import NamedTuple

type MapaPII = dict[str, str]


def _cpf_valido(valor: str) -> bool:
    d = [int(c) for c in valor if c.isdigit()]

    if len(set(d)) == 1:
        return False

    for n in (9, 10):
        resto = sum(x * (n + 1 - i) for i, x in enumerate(d[:n])) * 10 % 11 % 10
        if resto != d[n]:
            return False

    return True


def _cnpj_valido(valor: str) -> bool:
    d = [int(c) for c in valor if c.isdigit()]

    if len(set(d)) == 1:
        return False

    for n in (12, 13):
        pesos = [*range(n - 7, 1, -1), *range(9, 1, -1)][:n]
        resto = sum(x * p for x, p in zip(d[:n], pesos)) % 11
        if (0 if resto < 2 else 11 - resto) != d[n]:
            return False

    return True


class PIIPattern(NamedTuple):
    tipo: str
    padrao: str

    # False = contato (email/telefone): só a entrada anonimiza.
    redige_na_saida: bool = True

    # Filtra falso positivo do regex (ex.: 11 dígitos que não fecham o dígito verificador).
    valida: Callable[[str], bool] | None = None


PII: list[PIIPattern] = [
    # (?<!\d)/(?!\d): sem fronteira, 11 dígitos dentro de um número maior (ex.: nome "Arroz 1234567890123") viravam CPF.
    PIIPattern("CPF",       r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)", valida=_cpf_valido),
    PIIPattern("CNPJ",     r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)", valida=_cnpj_valido),
    PIIPattern("SENHA",     r"(?i)senha[:\s]+\S+"),
    PIIPattern("EMAIL",     r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", redige_na_saida=False),
    PIIPattern("TELEFONE",  r"(?<!\d)\(?\d{2}\)?\s?\d{4,5}-?\d{4}(?!\d)",      redige_na_saida=False),
]

PII_USUARIO: list[PIIPattern] = [p for p in PII if p.redige_na_saida]


def anonimizar_entrada(texto: str) -> tuple[str, MapaPII]:
    """Troca cada PII por um token único e devolve o texto limpo + o mapa pra reverter."""

    mapa: MapaPII = {}

    for pii in PII:
        for valor in re.findall(pii.padrao, texto):
            if pii.valida and not pii.valida(valor):
                continue

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
        texto = re.sub(
            pii.padrao,
            lambda m, pii=pii: m[0] if pii.valida and not pii.valida(m[0]) else f"[{pii.tipo} OMITIDO]",
            texto,
        )

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
