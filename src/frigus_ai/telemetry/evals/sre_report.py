"""
Relatório de SRE: custo estimado (100 e 1000 usuários/semana), índice de erros,
custo por resolução e ROI — lendo os contadores Prometheus que a API já expõe
(`telemetry/metrics.py`), sem tocar em código de runtime.

Definições assumidas (documentar aqui, não espalhar pelo código):

- **Resolução** = execução do grafo que terminou com `outcome="success"`
  (`frigus_graph_runs_total`) — passou pelo guardrail de saída e, quando aplicável,
  pelo juiz. `outcome="blocked"` (guardrail de entrada recusou) não é resolução nem erro.
- **Índice de erros** = `error` / total de turnos — o SLI de erro do SLO
  (`SLO_TAXA_ERRO` em `telemetry/metrics.py`). Bloqueio fica fora do numerador.
- **Janela**: tudo é `increase(...[JANELA])`, então soma entre reinícios da API e funciona com
  ela parada; o p95 de `frigus_graph_duration_seconds` ≤ `SLO_LATENCIA_P95_S` é `histogram_quantile`.
- **Preço por token**: `PRECOS_POR_1M_TOKENS` em `telemetry/metrics_callback.py` — a mesma
  tabela que alimenta `frigus_llm_cost_usd_total` em runtime.
- **Volume por usuário**: sem dado real de uso, `MENSAGENS_POR_USUARIO_SEMANA` = 20 (~3 por
  dia: uma consulta e uma ação), multiplicado pelo custo médio por turno observado.
- **Valor por resolução** (ROI): desperdício evitado por resposta. Uma família brasileira
  desperdiça ~R$ 1.002/ano em alimentos (Embrapa/FGV, 2018, sem correção pela inflação, ou
  seja, conservador); supõe-se que o Frigus evite 20% disso, rateado pelas 20 mensagens da
  semana, convertido a R$ 5,50/US$. As três premissas (20%, câmbio e volume) são estimativas.

Rodar: `python -m frigus_ai.telemetry.evals.sre_report` (usa `settings.observability.prometheus_url`; só
funciona com o Prometheus do `docker-compose.yml` no ar). `--demo` roda o self-check
sem depender de Prometheus.
"""

import math
import sys
from typing import TypedDict

import httpx

from frigus_ai.settings import settings
from frigus_ai.settings.llm import Model
from frigus_ai.telemetry.metrics import SLO_LATENCIA_P95_S, SLO_TAXA_ERRO
from frigus_ai.telemetry.metrics_callback import custo_usd

MENSAGENS_POR_USUARIO_SEMANA = 20  # estimativa, ver docstring
# R$ 1.002/ano de desperdício por família (Embrapa/FGV) x 20% evitado / 52 semanas / mensagens / câmbio
VALOR_POR_RESOLUCAO_USD = 1002 * 0.20 / 52 / MENSAGENS_POR_USUARIO_SEMANA / 5.50  # ≈ US$ 0,035
JANELA = "7d"


class TokensPorDirecao(TypedDict, total=False):
    input: float
    output: float


class Metricas(TypedDict):
    tokens: dict[str, TokensPorDirecao]
    graph_runs: dict[str, float]
    rate_limit_rejections: float
    latencia_p95_s: float | None


class Relatorio(TypedDict):
    janela: str
    total_turnos_observados: float
    resolucoes_observadas: float
    indice_erros: float
    bloqueios_guardrail: float
    latencia_p95_s: float | None
    slo_latencia_ok: bool | None
    slo_erro_ok: bool
    orcamento_de_erro_consumido: float
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
    resp = client.get(f"{settings.observability.prometheus_url}/api/v1/query", params={"query": promql})
    resp.raise_for_status()
    return resp.json()["data"]["result"]


def _somar_por_label(resultado: list[PromMetric], label: str) -> dict[str, float]:
    """Soma o valor de cada série, agrupado pelo label pedido (ex.: outcome, scope)."""

    somas: dict[str, float] = {}
    for item in resultado:
        chave = item["metric"].get(label, "unknown")
        somas[chave] = somas.get(chave, 0.0) + float(item["value"][1])
    return somas


def _acumulado(metrica: str, por: str) -> str:
    """`increase` soma entre reinícios da API (o contador zera) e continua valendo com ela parada."""

    return f"sum by ({por}) (increase({metrica}[{JANELA}]))"


def coletar_metricas(client: httpx.Client) -> Metricas:
    tokens: dict[str, TokensPorDirecao] = {}
    for item in _query(client, _acumulado("frigus_llm_tokens_total", "model, direction")):
        modelo = item["metric"].get("model", "unknown")
        direcao = item["metric"].get("direction", "unknown")
        tokens.setdefault(modelo, TokensPorDirecao())[direcao] = float(item["value"][1])

    graph_runs = _somar_por_label(_query(client, _acumulado("frigus_graph_runs_total", "outcome")), "outcome")
    rejeicoes = _somar_por_label(
        _query(client, _acumulado("frigus_rate_limit_rejections_total", "scope")), "scope"
    )

    p95 = _query(client, (
        "histogram_quantile(0.95, sum by (le) "
        f"(rate(frigus_graph_duration_seconds_bucket[{JANELA}])))"
    ))
    latencia_p95 = float(p95[0]["value"][1]) if p95 else None
    if latencia_p95 is not None and math.isnan(latencia_p95):  # sem turno na janela
        latencia_p95 = None

    return Metricas(
        tokens=tokens,
        graph_runs=graph_runs,
        rate_limit_rejections=sum(rejeicoes.values()),
        latencia_p95_s=latencia_p95,
    )


def _custo_total_usd(tokens: dict[str, TokensPorDirecao]) -> float:
    return sum(
        custo_usd(modelo, direcoes.get("input", 0.0), direcoes.get("output", 0.0))
        for modelo, direcoes in tokens.items()
    )


def gerar_relatorio(metricas: Metricas) -> Relatorio:
    graph_runs = metricas["graph_runs"]
    total_turnos = sum(graph_runs.values())
    resolucoes = graph_runs.get("success", 0.0)

    custo_total = _custo_total_usd(metricas["tokens"])
    custo_por_turno = custo_total / total_turnos if total_turnos else 0.0
    custo_por_resolucao = custo_total / resolucoes if resolucoes else 0.0
    indice_erros = graph_runs.get("error", 0.0) / total_turnos if total_turnos else 0.0
    p95 = metricas["latencia_p95_s"]

    return Relatorio(
        janela=f"últimos {JANELA} (increase do Prometheus; estimado, soma entre reinícios da API)",
        total_turnos_observados=total_turnos,
        resolucoes_observadas=resolucoes,
        indice_erros=indice_erros,
        bloqueios_guardrail=graph_runs.get("blocked", 0.0),
        latencia_p95_s=p95,
        slo_latencia_ok=None if p95 is None else p95 <= SLO_LATENCIA_P95_S,
        slo_erro_ok=indice_erros <= SLO_TAXA_ERRO,
        # 1.0 = gastou todo o espaço de falha combinado; acima disso o SLO estourou.
        orcamento_de_erro_consumido=indice_erros / SLO_TAXA_ERRO,
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
            Model.GEMINI_FLASH: TokensPorDirecao(input=1_000_000, output=500_000),
            Model.QWEN_3_8_FREE: TokensPorDirecao(input=1_000_000, output=1_000_000),
        },
        graph_runs={"success": 7, "blocked": 1, "error": 2},
        rate_limit_rejections=1,
        latencia_p95_s=5.0,
    )

    relatorio = gerar_relatorio(metricas)
    assert relatorio["custo_total_observado_usd"] == 0.30 * 1 + 2.50 * 0.5  # qwen free não soma nada
    assert relatorio["indice_erros"] == 0.2
    assert relatorio["total_turnos_observados"] == 10
    assert relatorio["resolucoes_observadas"] == 7
    assert relatorio["bloqueios_guardrail"] == 1
    assert relatorio["custo_por_resolucao_usd"] == relatorio["custo_total_observado_usd"] / 7
    assert relatorio["slo_latencia_ok"] is True
    assert relatorio["slo_erro_ok"] is False  # 20% > 5%
    assert relatorio["orcamento_de_erro_consumido"] == 0.2 / SLO_TAXA_ERRO
    assert relatorio["estimativa_100_usuarios_semana_usd"] == 100 * MENSAGENS_POR_USUARIO_SEMANA * (
        relatorio["custo_total_observado_usd"] / 10
    )
    vazio = Metricas(tokens={}, graph_runs={}, rate_limit_rejections=0, latencia_p95_s=None)
    assert gerar_relatorio(vazio)["indice_erros"] == 0.0
    assert gerar_relatorio(vazio)["slo_latencia_ok"] is None

    print("demo ok")


if __name__ == "__main__":
    demo() if "--demo" in sys.argv else main()
