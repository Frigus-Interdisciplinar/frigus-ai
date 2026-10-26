import { Card } from "./ui/card";

export interface Serie {
  label: string;
  // Classe de `stroke-*` e `bg-*` do tema, pra a linha e a legenda usarem a mesma cor.
  stroke: string;
  fundo: string;
  values: number[];
}

const LARGURA = 300;
const ALTURA = 100;

export function LineChart({
  title,
  series,
  format,
}: {
  title: string;
  series: Serie[];
  format: (n: number) => string;
}) {
  const pontos = series[0]?.values.length ?? 0;
  const max = Math.max(...series.flatMap((s) => s.values), 0);
  const topo = max > 0 ? max : 1;

  const caminho = (values: number[]) =>
    values
      .map((v, i) => `${(i / (pontos - 1)) * LARGURA},${ALTURA - (v / topo) * ALTURA}`)
      .join(" ");

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <span className="text-xs text-muted-foreground">pico {format(max)}</span>
      </div>

      {pontos < 2 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">coletando…</p>
      ) : (
        <svg viewBox={`0 0 ${LARGURA} ${ALTURA}`} preserveAspectRatio="none" className="h-24 w-full">
          <line x1="0" x2={LARGURA} y1={ALTURA} y2={ALTURA} className="stroke-border" vectorEffect="non-scaling-stroke" />
          <line x1="0" x2={LARGURA} y1="0" y2="0" className="stroke-border" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
          {series.map((s) => (
            <polyline
              key={s.label}
              points={caminho(s.values)}
              fill="none"
              strokeWidth="2"
              strokeLinejoin="round"
              className={s.stroke}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
      )}

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {series.map((s) => (
          <span key={s.label} className="flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 rounded-full ${s.fundo}`} />
            {s.label}
            <span className="text-foreground">{format(s.values.at(-1) ?? 0)}</span>
          </span>
        ))}
      </div>
    </Card>
  );
}
