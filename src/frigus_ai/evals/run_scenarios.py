"""
Roda os cenários de `evals/scenarios.py` contra o grafo de verdade e agrega um relatório.

Precisa de infra viva: Postgres/Mongo/Redis/Qdrant no ar (`docker-compose.yml`) e pelo
menos `GEMINI_API_KEY`/`GROQ_API_KEY` configuradas — é o mesmo caminho que uma
mensagem via API percorre (`services/runner.py`), só que com usuário de teste dedicado.

Rodar: `python -m frigus_ai.evals.run_scenarios`. `--demo` roda o self-check da lógica
de agregação/match de palavra-chave, sem tocar em infra nenhuma.
"""

import asyncio
import sys
import time
from typing import TypedDict
from uuid import uuid4

from frigus_ai.evals.scenarios import CENARIOS, Cenario
from frigus_ai.services import runner
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service


class ResultadoCenario(TypedDict):
    id: str
    dominio: str
    passou: bool
    resposta: str | None
    latencia_s: float
    erro: str | None


def _bateu_palavra_chave(resposta: str | None, palavras_chave: tuple[str, ...]) -> bool:
    if not resposta:
        return False

    resposta_normalizada = resposta.lower()
    return any(palavra.lower() in resposta_normalizada for palavra in palavras_chave)


async def _rodar_cenario(cenario: Cenario, user_id: str, stock_id: int | None) -> ResultadoCenario:
    session_id = f"eval-{cenario['id']}-{uuid4()}"
    inicio = time.perf_counter()

    try:
        resposta = await runner.executar(cenario["pergunta"], session_id, user_id, stock_id)
        erro = None
    except Exception as e:
        resposta, erro = None, str(e)

    latencia = time.perf_counter() - inicio
    passou = erro is None and _bateu_palavra_chave(resposta, cenario["palavras_chave"])

    return ResultadoCenario(
        id=cenario["id"], dominio=cenario["dominio"], passou=passou,
        resposta=resposta, latencia_s=latencia, erro=erro,
    )


async def rodar_todos() -> list[ResultadoCenario]:
    user_id = await user_service.obter_ou_criar_padrao()
    stock_id = await chat_service.iniciar_sessao(user_id)

    return [await _rodar_cenario(cenario, user_id, stock_id) for cenario in CENARIOS]


def _imprimir_relatorio(resultados: list[ResultadoCenario]) -> None:
    total = len(resultados)
    passaram = sum(1 for r in resultados if r["passou"])

    for r in resultados:
        status = "OK " if r["passou"] else "FAIL"
        print(f"[{status}] {r['id']} ({r['dominio']}) — {r['latencia_s']:.2f}s")
        if not r["passou"]:
            print(f"       resposta: {r['resposta']!r}")
            if r["erro"]:
                print(f"       erro: {r['erro']}")

    print(f"\n{passaram}/{total} cenários passaram.")


def main() -> None:
    resultados = asyncio.run(rodar_todos())
    _imprimir_relatorio(resultados)


def demo() -> None:
    """Self-check da lógica de match/agregação, sem depender de infra nenhuma."""

    assert _bateu_palavra_chave("Sua geladeira está vazia.", ("geladeira", "vazio")) is True
    assert _bateu_palavra_chave("Você gastou R$ 50.", ("gast",)) is True
    assert _bateu_palavra_chave("resposta qualquer", ("inexistente",)) is False
    assert _bateu_palavra_chave(None, ("qualquer",)) is False
    assert _bateu_palavra_chave("", ("qualquer",)) is False

    print("demo ok")


if __name__ == "__main__":
    demo() if "--demo" in sys.argv else main()
