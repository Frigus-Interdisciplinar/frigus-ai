"""
Carrega os prompts dos `.md` desta pasta. Cada arquivo é dividido em seções `## NOME` (a chave
fica em minúsculas); `sistema.md` guarda os blocos comuns a todos os agentes.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from frigus_ai.domain.models import Fatos

_PASTA = Path(__file__).parent
_MARCADOR_SECAO = "## "

_USAM_TOOLS_OBRIGATORIAS = frozenset({"compras", "estoque", "financeiro", "receitas"})


@lru_cache(maxsize=32)
def load_sections(nome_arquivo: str | Path) -> dict[str, str]:
    """Seções cruas do .md, sem o envelope de persona — pra quem monta o prompt na mão."""

    secoes: dict[str, list[str]] = {}
    atual: list[str] | None = None

    for linha in (_PASTA / nome_arquivo).read_text(encoding="utf-8").splitlines():
        if linha.startswith(_MARCADOR_SECAO):
            atual = secoes.setdefault(linha.removeprefix(_MARCADOR_SECAO).strip().lower(), [])
        elif atual is not None:
            atual.append(linha)

    return {nome: "\n".join(linhas).strip() for nome, linhas in secoes.items()}


def _sistema(secao: str, **campos: str) -> str:
    texto = load_sections("sistema.md")[secao]
    return texto.format(**campos) if campos else texto


def contexto_temporal() -> str:
    """Montado a cada chamada, nunca no import: senão a API viva diz "hoje" com a data em que subiu."""

    agora = datetime.now(UTC).astimezone()
    return _sistema("contexto_temporal", agora=agora.strftime("%A, %d de %B de %Y — %H:%M:%S %Z"))


def _juntar(valores: Sequence[str]) -> str:
    # Lista vazia é ausência de cadastro: "nenhuma" fazia o LLM afirmar que não há alergia.
    return ", ".join(valores) or "não informado"


def load_prompt(nome: str, fatos: Fatos | None = None, conversas: Sequence[str] = ()) -> str:
    """System prompt: persona, data, [tools obrigatórias], papel, [shots], [fatos], [conversas]."""

    secoes = load_sections(f"{nome}.md")
    if not secoes.get("papel"):
        raise ValueError(f"Prompt {nome}.md não tem a seção ## PAPEL")

    partes = [_sistema("persona"), contexto_temporal()]

    if nome in _USAM_TOOLS_OBRIGATORIAS:
        partes.append(_sistema("obrigatoriedade_tools"))

    partes.append(f"### PAPEL\n{secoes['papel']}")

    if shots := secoes.get("shots"):
        partes.append(shots)

    if fatos is not None:
        partes.append(_sistema(
            "fatos",
            alergias=_juntar(fatos.alergias),
            preferencias=_juntar(fatos.preferencias),
            restricoes=_juntar(fatos.restricoes),
            habitos=_juntar(fatos.habitos),
        ))

    if conversas:
        partes.append(_sistema("conversas", resumos="\n".join(f"- {c}" for c in conversas)))

    return "\n\n".join(partes)


__all__ = ["contexto_temporal", "load_prompt", "load_sections"]
