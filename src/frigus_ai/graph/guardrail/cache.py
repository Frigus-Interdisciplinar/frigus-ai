"""
Cache da classificação do guardrail de entrada.

O caminho determinístico (`padroes.py`) já evita a LLM nos casos óbvios, mas TODA mensagem
legítima ainda pagava uma chamada de modelo só pra ouvir "APROVADO". Num assistente de
geladeira as perguntas se repetem muito ("o que vence essa semana?"), então classificar o
mesmo texto de novo é gasto puro.

Cachear veredito é seguro — e até deixa a decisão mais estável, já que tira a variação do
modelo entre execuções idênticas. Duas proteções contra veredito velho:

- a chave carrega o fingerprint do prompt do classificador: editou `guardrail.md`, o cache
  antigo deixa de ser consultado sozinho, sem precisar limpar nada;
- TTL curto, pra qualquer ajuste de modelo/temperatura expirar em um dia.
"""

import hashlib
import re
import time

from frigus_ai.infra.redis.connection import get_client
from frigus_ai.infra.redis.keys import GUARDRAIL_TTL_TIME, chave_guardrail
from frigus_ai.logging import Logging

logger = Logging.get_logger("redis_guardrail")

# Com o Redis fora do ar, cada ida ao cache paga o timeout de conexão. Duas por mensagem
# (leitura + escrita) fariam o cache deixar o turno MAIS lento do que sem cache nenhum —
# então, depois de uma falha, o cache se desliga sozinho por um tempo.
# ponytail: pausa global simples; se um dia houver vários processos e valer a pena medir
# taxa de erro, troca por um circuit breaker de verdade.
_PAUSA_APOS_FALHA = 30.0
_silenciado_ate = 0.0


def _indisponivel() -> bool:
    return time.monotonic() < _silenciado_ate


def _registrar_falha(acao: str, erro: Exception) -> None:
    global _silenciado_ate

    _silenciado_ate = time.monotonic() + _PAUSA_APOS_FALHA
    logger.warning(
        "Cache do guardrail indisponível (%s): %s — pausado por %.0fs.",
        acao, erro, _PAUSA_APOS_FALHA,
    )

# `anonimizar_entrada` troca PII por `[PII_CPF_a3f9c1]`, com sufixo aleatório a cada
# chamada — sem normalizar, mensagem com PII nunca bateria no cache.
_TOKEN_PII = re.compile(r"\[PII_([A-Z]+)_[0-9a-f]{6}\]")


def _digest(texto: str, fingerprint: str) -> str:
    normalizado = _TOKEN_PII.sub(r"[PII_\1]", texto).strip().lower()

    return hashlib.sha256(f"{fingerprint}|{normalizado}".encode()).hexdigest()


def categoria_em_cache(texto: str, fingerprint: str) -> str | None:
    """Categoria já classificada, ou None — nunca levanta: sem cache, classifica na LLM."""

    if _indisponivel():
        return None

    try:
        return get_client().get(chave_guardrail(_digest(texto, fingerprint)))
    except Exception as e:
        _registrar_falha("leitura", e)
        return None


def guardar_categoria(texto: str, fingerprint: str, categoria: str) -> None:
    if _indisponivel():
        return

    try:
        get_client().set(
            chave_guardrail(_digest(texto, fingerprint)), categoria, ex=GUARDRAIL_TTL_TIME
        )
    except Exception as e:
        _registrar_falha("escrita", e)


def fingerprint_do_prompt(prompt: str) -> str:
    """8 hex do prompt do classificador — muda o prompt, muda o espaço de chaves."""

    return hashlib.sha256(prompt.encode()).hexdigest()[:8]


__all__ = ["categoria_em_cache", "fingerprint_do_prompt", "guardar_categoria"]
