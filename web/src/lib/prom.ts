// Parser mínimo do formato de exposição do Prometheus (texto de /metrics).
// Não cobre o formato completo (ex.: histograms com múltiplas linhas _bucket ficam soltas
// como séries normais) — o bastante pra somar counters e ler gauges/quantis num dashboard.
export interface PromSample {
  name: string;
  labels: Record<string, string>;
  value: number;
}

const LINE_RE = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{([^}]*)\})?\s+(\S+)$/;
const LABEL_RE = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"/g;

export function parseMetrics(text: string): PromSample[] {
  const samples: PromSample[] = [];
  for (const line of text.split("\n")) {
    if (!line || line.startsWith("#")) continue;
    const m = LINE_RE.exec(line.trim());
    if (!m) continue;
    const value = Number(m[4]);
    if (Number.isNaN(value)) continue;

    const labels: Record<string, string> = {};
    if (m[3]) {
      for (const lm of m[3].matchAll(LABEL_RE)) {
        labels[lm[1]] = lm[2];
      }
    }
    samples.push({ name: m[1], labels, value });
  }
  return samples;
}

export function sumByName(samples: PromSample[], name: string): number {
  return samples.filter((s) => s.name === name).reduce((acc, s) => acc + s.value, 0);
}

export function groupByLabel(
  samples: PromSample[],
  name: string,
  label: string,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const s of samples) {
    if (s.name !== name) continue;
    const key = s.labels[label] ?? "(sem label)";
    out[key] = (out[key] ?? 0) + s.value;
  }
  return out;
}

export interface HistogramStat {
  totalSeconds: number;
  count: number;
  avgSeconds: number;
}

// Histogram do Prometheus expõe `<base>_sum` (soma) e `<base>_count` (contagem) por combinação
// de labels — dá pra tirar o tempo total e médio gasto por node/tool/etc. sem precisar somar os
// buckets à mão feito é preciso fazer olhando o texto cru de /metrics.
export function histogramStatsByLabel(
  samples: PromSample[],
  baseName: string,
  label: string,
): Record<string, HistogramStat> {
  const totals = groupByLabel(samples, `${baseName}_sum`, label);
  const counts = groupByLabel(samples, `${baseName}_count`, label);

  const out: Record<string, HistogramStat> = {};
  for (const key of new Set([...Object.keys(totals), ...Object.keys(counts)])) {
    const totalSeconds = totals[key] ?? 0;
    const count = counts[key] ?? 0;
    out[key] = { totalSeconds, count, avgSeconds: count > 0 ? totalSeconds / count : 0 };
  }
  return out;
}

// Quantil de um histogram somando os buckets de todas as séries (mesma interpolação linear do
// `histogram_quantile` do Prometheus). Acumulado desde o start do processo — não é janela de 5m.
export function histogramQuantile(samples: PromSample[], baseName: string, q: number): number | null {
  const porLe = new Map<number, number>();
  for (const s of samples) {
    if (s.name !== `${baseName}_bucket`) continue;
    const le = s.labels.le === "+Inf" ? Infinity : Number(s.labels.le);
    porLe.set(le, (porLe.get(le) ?? 0) + s.value);
  }
  const buckets = [...porLe.entries()].sort((a, b) => a[0] - b[0]);
  const total = buckets.at(-1)?.[1] ?? 0;
  if (total === 0) return null;

  const alvo = q * total;
  let anteriorLe = 0;
  let anteriorCount = 0;
  for (const [le, count] of buckets) {
    if (count >= alvo) {
      if (le === Infinity) return anteriorLe; // além do maior bucket: o Prometheus devolve o maior limite
      return anteriorLe + ((le - anteriorLe) * (alvo - anteriorCount)) / (count - anteriorCount || 1);
    }
    anteriorLe = le;
    anteriorCount = count;
  }
  return anteriorLe;
}
