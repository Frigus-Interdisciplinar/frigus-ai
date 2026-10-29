"""
Roda os cenários de `telemetry/evals/scenarios.py` contra o grafo de verdade e agrega um relatório.

Precisa de infra viva: Postgres/Mongo/Redis/Qdrant no ar (`docker-compose.yml`) e pelo
menos `GEMINI_API_KEY`/`GROQ_API_KEY` configuradas — é o mesmo caminho que uma
mensagem via API percorre (`services/runner.py`), só que com usuário de teste dedicado.

Rodar: `python -m frigus_ai.telemetry.evals.run_scenarios [--rodadas N]`. `--demo` roda o self-check da lógica
de agregação/match de palavra-chave, sem tocar em infra nenhuma.
"""

import asyncio
import statistics
import sys
import time
from collections import defaultdict
from typing import TypedDict
from uuid import uuid4

from prometheus_client import REGISTRY

from frigus_ai.services import runner
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service
from frigus_ai.telemetry.evals.scenarios import CENARIOS, Cenario
from frigus_ai.telemetry.evals.sre_report import (
    Metricas,
    TokensPorDirecao,
    gerar_relatorio,
)


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


async def rodar_todos(rodadas: int = 1) -> list[ResultadoCenario]:
    user_id = await user_service.obter_ou_criar_padrao()
    stock_id = await chat_service.iniciar_sessao(user_id)

    return [
        await _rodar_cenario(cenario, user_id, stock_id)
        for _ in range(rodadas)
        for cenario in CENARIOS
    ]


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

    latencias = sorted(r["latencia_s"] for r in resultados)
    p95 = latencias[min(total - 1, int(total * 0.95))]
    print(f"latência: mediana {statistics.median(latencias):.1f}s, p95 {p95:.1f}s, máx {latencias[-1]:.1f}s")


def _imprimir_sre(resultados: list[ResultadoCenario]) -> None:
    """Custo, erros e tempo por node das métricas do próprio processo (mesmos contadores do /metrics)."""

    tokens: dict[str, TokensPorDirecao] = {}
    graph_runs: dict[str, float] = defaultdict(float)
    tempo_node: dict[str, float] = defaultdict(float)

    for familia in REGISTRY.collect():
        for amostra in familia.samples:
            rotulos = amostra.labels
            if amostra.name == "frigus_llm_tokens_total":
                tokens.setdefault(rotulos["model"], TokensPorDirecao())[rotulos["direction"]] = amostra.value
            elif amostra.name == "frigus_graph_runs_total":
                graph_runs[rotulos["outcome"]] += amostra.value
            elif amostra.name == "frigus_node_duration_seconds_sum":
                tempo_node[rotulos["node"]] += amostra.value

    latencias = sorted(r["latencia_s"] for r in resultados)
    p95 = latencias[min(len(latencias) - 1, int(len(latencias) * 0.95))]
    relatorio = gerar_relatorio(
        Metricas(tokens=tokens, graph_runs=dict(graph_runs), rate_limit_rejections=0, latencia_p95_s=p95)
    )

    print("\n--- SRE (métricas do processo) ---")
    for chave, valor in relatorio.items():
        print(f"{chave}: {valor}")

    total_node = sum(tempo_node.values()) or 1.0
    print("\ntempo por node:")
    for node, segundos in sorted(tempo_node.items(), key=lambda kv: -kv[1]):
        print(f"  {node}: {segundos:.1f}s ({segundos / total_node:.0%})")


def main() -> None:
    rodadas = int(sys.argv[sys.argv.index("--rodadas") + 1]) if "--rodadas" in sys.argv else 1
    resultados = asyncio.run(rodar_todos(rodadas))
    _imprimir_relatorio(resultados)
    _imprimir_sre(resultados)


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
