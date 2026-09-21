"""
Detecção de ataque do guardrail: jailbreak/prompt injection e tentativa de extrair dado
interno. É o caminho barato — roda antes de gastar qualquer chamada de LLM.

Só o guardrail usa isto. Os regex de PII moram em `frigus_ai/privacy.py`, que é neutro
porque repository e service também precisam anonimizar.

Os padrões são compilados uma vez no import: `re` até cacheia internamente, mas compilar
explícito deixa claro que a lista é fixa e tira a busca no cache do caminho quente.
"""

import re

_PADROES_INJECAO = [
    r"ignore\s+(as\s+)?instru[çc][oõ]es",
    r"ignore\s+previous\s+instructions",
    r"forget\s+your\s+instructions",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+)?",
    r"pretend\s+(you\s+are|to\s+be)",
    r"jailbreak",
    r"dan\s+mode",
    r"modo\s+irrestrito",
    r"system\s*prompt",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"###\s*instruction",
    r"override\s+(your\s+)?instructions",
    r"desconsider[ea]\s+(suas\s+)?instru[çc][oõ]es",
]

INJECAO = [re.compile(p, re.IGNORECASE) for p in _PADROES_INJECAO]

KEYWORDS_DADOS_INTERNOS = [
    "prompt do sistema", "system prompt", "suas instruções", "your instructions",
    "variável de ambiente", "chave de api", "api key", "senha do sistema",
    "token de acesso", "banco de dados interno", "tabela interna",
    "dados de outros usuários", "lista de usuários", "credenciais",
    "hash_password", "search_path",
]


def tem_injecao(texto: str) -> bool:
    return any(padrao.search(texto) for padrao in INJECAO)


def pede_dado_interno(texto: str) -> bool:
    minusculo = texto.lower()
    return any(palavra in minusculo for palavra in KEYWORDS_DADOS_INTERNOS)


__all__ = [
    "INJECAO",
    "KEYWORDS_DADOS_INTERNOS",
    "pede_dado_interno",
    "tem_injecao",
]
