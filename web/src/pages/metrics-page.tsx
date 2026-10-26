import { useEffect, useState } from "react";
import { Link } from "react-router";
import { LineChart, type Serie } from "../components/line-chart";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { getMetricsToken, setMetricsToken } from "../lib/auth";
import { cn } from "../lib/cn";
import {
  groupByLabel,
  histogramQuantile,
  histogramStatsByLabel,
  parseMetrics,
  sumByName,
  type HistogramStat,
  type PromSample,
} from "../lib/prom";

const INTERVALO_MS = 15_000;
// 120 leituras de 15s = 30 min de histórico, só na memória da aba.
const MAX_PONTOS = 120;

interface Leitura {
  t: number;
  ok: number;
  bloqueados: number;
  erros: number;
  durSoma: number;
  durContagem: number;
  custo: number;
  tokensIn: number;
  tokensOut: number;
  emAndamento: number;
}

function leitura(samples: PromSample[]): Leitura {
  const turnos = (outcome: string) =>
    sumByName(samples.filter((s) => s.labels.outcome === outcome), "frigus_graph_runs_total");
  const tokens = (direction: string) =>
    sumByName(samples.filter((s) => s.labels.direction === direction), "frigus_llm_tokens_total");

  return {
    t: Date.now(),
    ok: turnos("success"),
    bloqueados: turnos("blocked"),
    erros: turnos("error"),
    durSoma: sumByName(samples, "frigus_graph_duration_seconds_sum"),
    durContagem: sumByName(samples, "frigus_graph_duration_seconds_count"),
    custo: sumByName(samples, "frigus_llm_cost_usd_total"),
    tokensIn: tokens("input"),
    tokensOut: tokens("output"),
    emAndamento: sumByName(samples, "frigus_graph_in_progress"),
  };
}

// Contadores só crescem; o delta entre leituras vira "por minuto". Delta negativo = a API reiniciou.
function porMinuto(h: Leitura[], campo: (l: Leitura) => number): number[] {
  return h.slice(1).map((l, i) => {
    const delta = campo(l) - campo(h[i]);
    return delta > 0 ? (delta * 60_000) / (l.t - h[i].t) : 0;
  });
}

function latenciaMedia(h: Leitura[]): number[] {
  return h.slice(1).map((l, i) => {
    const turnos = l.durContagem - h[i].durContagem;
    return turnos > 0 ? (l.durSoma - h[i].durSoma) / turnos : 0;
  });
}

function Kpi({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
    </Card>
  );
}

function Breakdown({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));

  return (
    <Card className="p-4">
      <p className="mb-3 text-sm font-medium text-foreground">{title}</p>
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">sem dados</p>
      ) : (
        <div className="flex flex-col gap-2">
          {entries.map(([key, value]) => (
            <div key={key} className="flex items-center gap-2 text-sm">
              <span className="w-32 shrink-0 truncate text-muted-foreground">{key}</span>
              <div className="h-2 flex-1 rounded bg-muted">
                <div
                  className="h-2 rounded bg-primary"
                  style={{ width: `${(value / max) * 100}%` }}
                />
              </div>
              <span className="w-12 shrink-0 text-right text-foreground">{value}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function fmtSeconds(s: number): string {
  return s < 10 ? `${s.toFixed(2)}s` : `${s.toFixed(1)}s`;
}

// Quanto tempo cada label consumiu em relação ao total somado de todas — é o que responde
// "o guardrail comeu 30 dos 35s do grafo" sem precisar ler os buckets do histogram na mão.
function TimeBreakdown({ title, stats }: { title: string; stats: Record<string, HistogramStat> }) {
  const entries = Object.entries(stats).sort((a, b) => b[1].totalSeconds - a[1].totalSeconds);
  const totalGeral = entries.reduce((acc, [, v]) => acc + v.totalSeconds, 0) || 1;

  return (
    <Card className="p-4">
      <p className="mb-3 text-sm font-medium text-foreground">{title}</p>
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">sem dados</p>
      ) : (
        <div className="flex flex-col gap-2">
          {entries.map(([key, stat]) => {
            const pct = (stat.totalSeconds / totalGeral) * 100;
            return (
              <div key={key} className="flex items-center gap-2 text-sm">
                <span className="w-28 shrink-0 truncate text-muted-foreground">{key}</span>
                <div className="h-2 flex-1 rounded bg-muted">
                  <div
                    className={pct >= 50 ? "h-2 rounded bg-destructive" : "h-2 rounded bg-primary"}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right text-foreground">{fmtSeconds(stat.totalSeconds)}</span>
                <span className="w-10 shrink-0 text-right text-muted-foreground">{pct.toFixed(0)}%</span>
                <span className="w-16 shrink-0 text-right text-muted-foreground">
                  méd {fmtSeconds(stat.avgSeconds)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

export function MetricsPage() {
  const [samples, setSamples] = useState<PromSample[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [historico, setHistorico] = useState<Leitura[]>([]);
  const [pedeToken, setPedeToken] = useState(false);
  const [tokenDigitado, setTokenDigitado] = useState("");
  const [token, setToken] = useState(getMetricsToken() ?? "");

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      try {
        const res = await fetch("/metrics", { headers: token ? { Authorization: `Bearer ${token}` } : {} });
        if (res.status === 401) {
          // O /metrics tem segredo próprio (o do Prometheus), diferente da API key do usuário.
          if (!cancelado) setPedeToken(true);
          return;
        }
        if (!res.ok) throw new Error(`erro ${res.status}`);
        const text = await res.text();
        if (cancelado) return;
        setPedeToken(false);
        setErro(null);
        const lidas = parseMetrics(text);
        setSamples(lidas);
        setHistorico((h) => [...h, leitura(lidas)].slice(-MAX_PONTOS));
      } catch {
        if (!cancelado) setErro("Não consegui carregar /metrics.");
      }
    }

    carregar();
    const id = setInterval(carregar, INTERVALO_MS);
    return () => {
      cancelado = true;
      clearInterval(id);
    };
  }, [token]);

  const httpTotal = samples ? sumByName(samples, "frigus_http_requests_total") : 0;
  const httpAtivos = samples ? sumByName(samples, "frigus_http_active_requests") : 0;
  const graphRuns = samples ? sumByName(samples, "frigus_graph_runs_total") : 0;
  const graphOk = samples ? sumByName(samples.filter((s) => s.labels.outcome === "success"), "frigus_graph_runs_total") : 0;
  const tokensIn = samples ? sumByName(samples.filter((s) => s.labels.direction === "input"), "frigus_llm_tokens_total") : 0;
  const tokensOut = samples ? sumByName(samples.filter((s) => s.labels.direction === "output"), "frigus_llm_tokens_total") : 0;
  const rateLimited = samples ? sumByName(samples, "frigus_rate_limit_rejections_total") : 0;

  const graphDurSum = samples ? sumByName(samples, "frigus_graph_duration_seconds_sum") : 0;
  const graphDurCount = samples ? sumByName(samples, "frigus_graph_duration_seconds_count") : 0;
  const graphDurAvg = graphDurCount > 0 ? graphDurSum / graphDurCount : 0;

  // SLO do turno: limites vêm da própria API (`frigus_slo_target`), não ficam repetidos aqui.
  const sloTarget = (sli: string) =>
    samples?.find((s) => s.name === "frigus_slo_target" && s.labels.sli === sli)?.value ?? null;
  const sloLatencia = sloTarget("latency_p95_seconds");
  const sloErro = sloTarget("error_ratio");
  const graphErros = samples ? sumByName(samples.filter((s) => s.labels.outcome === "error"), "frigus_graph_runs_total") : 0;
  const graphBloqueios = samples ? sumByName(samples.filter((s) => s.labels.outcome === "blocked"), "frigus_graph_runs_total") : 0;
  const taxaErro = graphRuns > 0 ? graphErros / graphRuns : 0;
  const p95 = samples ? histogramQuantile(samples, "frigus_graph_duration_seconds", 0.95) : null;
  const sloOk = p95 !== null && sloLatencia !== null && sloErro !== null && p95 <= sloLatencia && taxaErro <= sloErro;
  const custoUsd = samples ? sumByName(samples, "frigus_llm_cost_usd_total") : 0;
  const fallbacks = samples ? sumByName(samples, "frigus_llm_fallbacks_total") : 0;
  const jevDecisoes = samples ? sumByName(samples, "frigus_jev_decisions_total") : 0;
  const jevConfSoma = samples ? sumByName(samples, "frigus_jev_confidence_sum") : 0;
  const jevConfContagem = samples ? sumByName(samples, "frigus_jev_confidence_count") : 0;
  const emAndamento = samples ? sumByName(samples, "frigus_graph_in_progress") : 0;

  const nodeStats = samples ? histogramStatsByLabel(samples, "frigus_node_duration_seconds", "node") : {};
  const nodeTotalTime = Object.values(nodeStats).reduce((acc, s) => acc + s.totalSeconds, 0);
  const nodeMaisLento = Object.entries(nodeStats).sort((a, b) => b[1].totalSeconds - a[1].totalSeconds)[0];

  const graficos: { title: string; series: Serie[]; format: (n: number) => string }[] = [
    {
      title: "turnos por minuto",
      format: (n) => n.toFixed(1),
      series: [
        { label: "ok", stroke: "stroke-primary", fundo: "bg-primary", values: porMinuto(historico, (l) => l.ok) },
        { label: "bloqueados", stroke: "stroke-muted-foreground", fundo: "bg-muted-foreground", values: porMinuto(historico, (l) => l.bloqueados) },
        { label: "erro", stroke: "stroke-destructive", fundo: "bg-destructive", values: porMinuto(historico, (l) => l.erros) },
      ],
    },
    {
      title: "latência média do turno",
      format: fmtSeconds,
      series: [{ label: "média na janela", stroke: "stroke-primary", fundo: "bg-primary", values: latenciaMedia(historico) }],
    },
    {
      title: "tokens por minuto",
      format: (n) => n.toFixed(0),
      series: [
        { label: "entrada", stroke: "stroke-primary", fundo: "bg-primary", values: porMinuto(historico, (l) => l.tokensIn) },
        { label: "saída", stroke: "stroke-muted-foreground", fundo: "bg-muted-foreground", values: porMinuto(historico, (l) => l.tokensOut) },
      ],
    },
    {
      title: "custo LLM por minuto (US$)",
      format: (n) => n.toFixed(4),
      series: [{ label: "custo", stroke: "stroke-primary", fundo: "bg-primary", values: porMinuto(historico, (l) => l.custo) }],
    },
  ];

  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <header className="flex items-baseline justify-between">
          <h1 className="font-display text-xl font-semibold text-foreground">Métricas</h1>
          <Link to="/chat" className="text-sm text-muted-foreground hover:text-foreground">
            voltar ao chat
          </Link>
        </header>

        {erro && <p className="text-sm text-destructive">{erro}</p>}

        {pedeToken && (
          <Card className="flex flex-col gap-3 p-4">
            <p className="text-sm text-foreground">
              O <code>/metrics</code> pede o token do Prometheus (<code>API_KEYS__METRICS_TOKEN</code>).
            </p>
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                const novo = tokenDigitado.trim();
                setMetricsToken(novo);
                setToken(novo);
              }}
            >
              <Input
                type="password"
                value={tokenDigitado}
                onChange={(e) => setTokenDigitado(e.target.value)}
                placeholder="cole o token"
                required
              />
              <Button type="submit">Salvar</Button>
            </form>
          </Card>
        )}

        {samples && sloLatencia !== null && sloErro !== null && (
          <div
            className={cn(
              "rounded-lg border px-4 py-3 text-sm",
              graphRuns === 0
                ? "border-border text-muted-foreground"
                : sloOk
                  ? "border-emerald-500/40 bg-emerald-500/10 text-foreground"
                  : "border-destructive/50 bg-destructive/10 text-foreground",
            )}
          >
            <strong className="font-semibold">
              {graphRuns === 0 ? "sem turnos ainda" : sloOk ? "dentro do SLO" : "SLO estourado"}
            </strong>
            <span className="ml-2 text-muted-foreground">
              p95 até {fmtSeconds(sloLatencia)} e erro até {(sloErro * 100).toFixed(0)}% — acumulado
              desde que a API subiu (janela de 5m e alertas no Prometheus).
            </span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Kpi label="requests HTTP" value={httpTotal} />
          <Kpi label="requests ativos" value={httpAtivos} />
          <Kpi label="runs do grafo" value={`${graphOk}/${graphRuns}`} />
          <Kpi label="rate limit rejeitados" value={rateLimited} />
          <Kpi label="duração média do grafo" value={fmtSeconds(graphDurAvg)} />
          <Kpi
            label="node mais lento"
            value={nodeMaisLento ? `${nodeMaisLento[0]} (${fmtSeconds(nodeMaisLento[1].totalSeconds)})` : "-"}
          />
          <Kpi label="tokens entrada" value={tokensIn} />
          <Kpi label="tokens saída" value={tokensOut} />
          <Kpi label="p95 do turno" value={p95 === null ? "-" : fmtSeconds(p95)} />
          <Kpi label="taxa de erro" value={`${(taxaErro * 100).toFixed(1)}%`} />
          <Kpi label="bloqueios (guardrail)" value={graphBloqueios} />
          <Kpi label="turnos em andamento" value={emAndamento} />
          <Kpi label="custo LLM (tabela fixa)" value={`US$ ${custoUsd.toFixed(4)}`} />
          <Kpi label="fallbacks de modelo" value={fallbacks} />
          <Kpi label="decisões do JeV" value={jevDecisoes} />
          <Kpi
            label="confiança média do JeV"
            value={jevConfContagem > 0 ? `${((jevConfSoma / jevConfContagem) * 100).toFixed(0)}%` : "-"}
          />
        </div>

        <section className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">
            ao vivo: uma leitura a cada {INTERVALO_MS / 1000}s, até {(MAX_PONTOS * INTERVALO_MS) / 60_000} min,
            só nesta aba (recarregar a página zera).
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {graficos.map((g) => (
              <LineChart key={g.title} {...g} />
            ))}
          </div>
        </section>

        {samples && (
          <>
            <TimeBreakdown title="tempo por node (soma / % do total / média por execução)" stats={nodeStats} />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Breakdown title="nodes do grafo" data={groupByLabel(samples, "frigus_node_runs_total", "node")} />
              <TimeBreakdown
                title="tempo por tool"
                stats={histogramStatsByLabel(samples, "frigus_tool_duration_seconds", "tool")}
              />
              <Breakdown title="LLM por modelo" data={groupByLabel(samples, "frigus_llm_runs_total", "model")} />
              <TimeBreakdown
                title="tempo por modelo LLM"
                stats={histogramStatsByLabel(samples, "frigus_llm_duration_seconds", "model")}
              />
              <Breakdown title="tools" data={groupByLabel(samples, "frigus_tool_runs_total", "tool")} />
              <Breakdown title="rotas do router" data={groupByLabel(samples, "frigus_router_decisions_total", "route")} />
              <Breakdown title="JeV por uso" data={groupByLabel(samples, "frigus_jev_decisions_total", "uso")} />
              <Breakdown title="JeV: quem respondeu (JeV ou reserva)" data={groupByLabel(samples, "frigus_jev_decisions_total", "modelo")} />
              <TimeBreakdown
                title="latência do JeV"
                stats={histogramStatsByLabel(
                  samples.filter((s) => s.labels.target === "jev"),
                  "frigus_external_call_duration_seconds",
                  "target",
                )}
              />
            </div>
          </>
        )}

        {nodeTotalTime === 0 && samples && (
          <p className="text-xs text-muted-foreground">
            sem histórico de duração ainda — manda uma mensagem no chat pra gerar dados aqui.
          </p>
        )}
      </div>
    </div>
  );
}
