import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Card } from "../components/ui/card";
import {
  groupByLabel,
  histogramStatsByLabel,
  parseMetrics,
  sumByName,
  type HistogramStat,
  type PromSample,
} from "../lib/prom";

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

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      try {
        const res = await fetch("/metrics");
        if (!res.ok) throw new Error(`erro ${res.status}`);
        const text = await res.text();
        if (!cancelado) setSamples(parseMetrics(text));
      } catch {
        if (!cancelado) setErro("Não consegui carregar /metrics.");
      }
    }

    carregar();
    const id = setInterval(carregar, 15_000);
    return () => {
      cancelado = true;
      clearInterval(id);
    };
  }, []);

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

  const nodeStats = samples ? histogramStatsByLabel(samples, "frigus_node_duration_seconds", "node") : {};
  const nodeTotalTime = Object.values(nodeStats).reduce((acc, s) => acc + s.totalSeconds, 0);
  const nodeMaisLento = Object.entries(nodeStats).sort((a, b) => b[1].totalSeconds - a[1].totalSeconds)[0];

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
        </div>

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
