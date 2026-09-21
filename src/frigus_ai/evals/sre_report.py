"""
Relatório de SRE: custo estimado (100 e 1000 usuários/semana), índice de erros,
custo por resolução e ROI — lendo os contadores Prometheus que a API já expõe
(`evals/metrics.py`), sem tocar em código de runtime.

Definições assumidas (documentar aqui, não espalhar pelo código):

- **Resolução** = execução do grafo que terminou com `outcome="success"`
  (`frigus_graph_runs_total`) — passou pelo guardrail de saída e, quando aplicável,
  pelo juiz.
- **Preço por token**: tabela `PRECOS_POR_1M_TOKENS` abaixo, em USD, por modelo (ver
  `frigus_ai.models.Model`) — preços de lista publicados pelos providers no momento em
  que este arquivo foi escrito. Conferir contra a página de pricing atual antes de usar
  em relatório oficial; providers mudam preço sem aviso.
- **Volume dos cenários**: sem dado real de uso, a estimativa multiplica
  `MENSAGENS_POR_USUARIO_SEMANA` (placeholder) pelo custo médio por turno observado.
- **Valor por resolução** (ROI): `VALOR_POR_RESOLUCAO_USD` é placeholder — não há dado
  de negócio real (ex.: valor do desperdício evitado por resposta) ainda.

Rodar: `python -m frigus_ai.evals.sre_report` (usa `settings.PROMETHEUS_URL`; só
funciona com o Prometheus do `docker-compose.yml` no ar). `--demo` roda o self-check
sem depender de Prometheus.
"""

import sys
from typing import NamedTuple, TypedDict

import httpx

from frigus_ai.models import Model
from frigus_ai.settings import settings


class PrecoPor1MTokens(NamedTuple):
    entrada: float
    saida: float


PRECOS_POR_1M_TOKENS: dict[str, PrecoPor1MTokens] = {
    Model.GEMINI_2_5_FLASH: PrecoPor1MTokens(entrada=0.30, saida=2.50),
    Model.LLAMA_3_3_VERSATILE: PrecoPor1MTokens(entrada=0.59, saida=0.79),
    Model.GLM_5_2_FREE: PrecoPor1MTokens(entrada=0.0, saida=0.0),
}

MENSAGENS_POR_USUARIO_SEMANA = 20  # placeholder — sem dado real de uso ainda
VALOR_POR_RESOLUCAO_USD = 0.0  # placeholder — sem dado de negócio real ainda


class TokensPorDirecao(TypedDict, total=False):
    input: float
    output: float


class Metricas(TypedDict):
    tokens: dict[str, TokensPorDirecao]
    graph_runs: dict[str, float]
    rate_limit_rejections: float


class Relatorio(TypedDict):
    janela: str
    total_turnos_observados: float
    resolucoes_observadas: float
    indice_erros: float
    rate_limit_rejections: float
    custo_total_observado_usd: float
    custo_medio_por_turno_usd: float
    custo_por_resolucao_usd: float
    roi_usd: float
    estimativa_100_usuarios_semana_usd: float
    estimativa_1000_usuarios_semana_usd: float


class PromMetric(TypedDict):
    metric: dict[str, str]
    value: tuple[float, str]


def _query(client: httpx.Client, promql: str) -> list[PromMetric]:
    resp = client.get(f"{settings.PROMETHEUS_URL}/api/v1/query", params={"query": promql})
    resp.raise_for_status()
    return resp.json()["data"]["result"]


def _somar_por_label(resultado: list[PromMetric], label: str) -> dict[str, float]:
    """Soma o valor de cada série, agrupado pelo label pedido (ex.: outcome, scope)."""

    somas: dict[str, float] = {}
    for item in resultado:
        chave = item["metric"].get(label, "unknown")
        somas[chave] = somas.get(chave, 0.0) + float(item["value"][1])
    return somas


def coletar_metricas(client: httpx.Client) -> Metricas:
    tokens: dict[str, TokensPorDirecao] = {}
    for item in _query(client, "frigus_llm_tokens_total"):
        modelo = item["metric"].get("model", "unknown")
        direcao = item["metric"].get("direction", "unknown")
        tokens.setdefault(modelo, TokensPorDirecao())[direcao] = float(item["value"][1])

    graph_runs = _somar_por_label(_query(client, "frigus_graph_runs_total"), "outcome")
    rejeicoes = _somar_por_label(_query(client, "frigus_rate_limit_rejections_total"), "scope")

    return Metricas(tokens=tokens, graph_runs=graph_runs, rate_limit_rejections=sum(rejeicoes.values()))


def _custo_total_usd(tokens: dict[str, TokensPorDirecao]) -> float:
    total = 0.0
    for modelo, direcoes in tokens.items():
        preco = PRECOS_POR_1M_TOKENS.get(modelo, PrecoPor1MTokens(0.0, 0.0))
        total += direcoes.get("input", 0.0) / 1_000_000 * preco.entrada
        total += direcoes.get("output", 0.0) / 1_000_000 * preco.saida
    return total


def gerar_relatorio(metricas: Metricas) -> Relatorio:
    graph_runs = metricas["graph_runs"]
    total_turnos = sum(graph_runs.values())
    resolucoes = graph_runs.get("success", 0.0)

    custo_total = _custo_total_usd(metricas["tokens"])
    custo_por_turno = custo_total / total_turnos if total_turnos else 0.0
    custo_por_resolucao = custo_total / resolucoes if resolucoes else 0.0

    return Relatorio(
        janela="acumulado desde o último restart do processo (contador Prometheus, não range query)",
        total_turnos_observados=total_turnos,
        resolucoes_observadas=resolucoes,
        indice_erros=graph_runs.get("error", 0.0) / total_turnos if total_turnos else 0.0,
        rate_limit_rejections=metricas["rate_limit_rejections"],
        custo_total_observado_usd=custo_total,
        custo_medio_por_turno_usd=custo_por_turno,
        custo_por_resolucao_usd=custo_por_resolucao,
        roi_usd=(VALOR_POR_RESOLUCAO_USD - custo_por_resolucao) * resolucoes,
        estimativa_100_usuarios_semana_usd=100 * MENSAGENS_POR_USUARIO_SEMANA * custo_por_turno,
        estimativa_1000_usuarios_semana_usd=1000 * MENSAGENS_POR_USUARIO_SEMANA * custo_por_turno,
    )


def main() -> None:
    with httpx.Client(timeout=10.0) as client:
        relatorio = gerar_relatorio(coletar_metricas(client))
    for chave, valor in relatorio.items():
        print(f"{chave}: {valor}")


def demo() -> None:
    """Self-check da lógica de cálculo, sem depender de Prometheus no ar."""

    metricas = Metricas(
        tokens={
            Model.GEMINI_2_5_FLASH: TokensPorDirecao(input=1_000_000, output=500_000),
            Model.GLM_5_2_FREE: TokensPorDirecao(input=1_000_000, output=1_000_000),
        },
        graph_runs={"success": 8, "error": 2},
        rate_limit_rejections=1,
    )

    relatorio = gerar_relatorio(metricas)
    assert relatorio["custo_total_observado_usd"] == 0.30 * 1 + 2.50 * 0.5  # glm free não soma nada
    assert relatorio["indice_erros"] == 0.2
    assert relatorio["total_turnos_observados"] == 10
    assert relatorio["resolucoes_observadas"] == 8
    assert relatorio["custo_por_resolucao_usd"] == relatorio["custo_total_observado_usd"] / 8
    assert relatorio["estimativa_100_usuarios_semana_usd"] == 100 * MENSAGENS_POR_USUARIO_SEMANA * (
        relatorio["custo_total_observado_usd"] / 10
    )
    vazio = Metricas(tokens={}, graph_runs={}, rate_limit_rejections=0)
    assert gerar_relatorio(vazio)["indice_erros"] == 0.0

    print("demo ok")


if __name__ == "__main__":
    demo() if "--demo" in sys.argv else main()
