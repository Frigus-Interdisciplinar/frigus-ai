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

type MapaPII = dict[str, str]
type PIIPattern = tuple[str, str]


# PII do usuário — redigida na entrada E na saída.
PII_USUARIO: list[PIIPattern] = [
    ("CPF",   r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"),
    ("CNPJ",  r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"),
    ("SENHA", r"(?i)senha[:\s]+\S+"),
]

# Conjunto completo: o do usuário + contatos, que só são anonimizados na entrada.
PII: list[PIIPattern] = PII_USUARIO + [
    ("EMAIL",    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    ("TELEFONE", r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}"),
]


def anonimizar_entrada(texto: str) -> tuple[str, MapaPII]:
    """Troca cada PII por um token único e devolve o texto limpo + o mapa pra reverter."""

    mapa: MapaPII = {}

    for tipo, padrao in PII:
        for valor in re.findall(padrao, texto):
            token = f"[PII_{tipo}_{uuid.uuid4().hex[:6]}]"
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

    for tipo, padrao in padroes if padroes is not None else PII:
        texto = re.sub(padrao, f"[{tipo} OMITIDO]", texto)

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
