import { cn } from "../../lib/cn";
import { GRAPH_EDGES, NODE_META, VIEWBOX } from "../../lib/graph-layout";
import type { GraphStatus, GraphTimings, NodeStatus } from "../../lib/use-execution-graph";
import { useTick } from "../../lib/use-tick";
import type { NodeName } from "../../types";
import { NodeIcon } from "./node-icon";

const SQUISHY = "transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)]";

const NODE_TEXT_CLASS: Record<NodeStatus, string> = {
  idle: "text-muted-foreground",
  active: "text-primary-foreground",
  done: "text-foreground",
};

const NODE_FILL_CLASS: Record<NodeStatus, string> = {
  idle: "fill-muted",
  active: "fill-primary",
  done: "fill-card",
};

const NODE_STROKE_CLASS: Record<NodeStatus, string> = {
  idle: "stroke-border",
  active: "stroke-primary",
  done: "stroke-primary",
};

function formatDuracao(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

export function GraphView({
  status,
  timings,
  activeEdge,
}: {
  status: GraphStatus;
  timings: GraphTimings;
  activeEdge: string | null;
}) {
  useTick(Object.values(status).includes("active"));

  return (
    <svg viewBox={VIEWBOX} className="mx-auto w-full max-w-[680px]" role="img" aria-label="Progresso da execução">
      {GRAPH_EDGES.map(([from, to]) => {
        const a = NODE_META[from];
        const b = NODE_META[to];
        const lit = activeEdge === `${from}>${to}`;
        const traveled = status[from] === "done" || status[from] === "active";

        const y1 = a.y + 52;
        const y2 = b.y - 52;
        const midY = (y1 + y2) / 2;

        return (
          <path
            key={`${from}>${to}`}
            d={`M ${a.x} ${y1} C ${a.x} ${midY}, ${b.x} ${midY}, ${b.x} ${y2}`}
            fill="none"
            strokeWidth={lit ? 5 : 2.5}
            strokeLinecap="round"
            className={cn(
              "transition-all duration-500",
              lit ? "edge-flow stroke-primary" : traveled ? "stroke-primary/40" : "stroke-border",
            )}
          />
        );
      })}

      {(Object.entries(NODE_META) as [NodeName, (typeof NODE_META)[NodeName]][]).map(([id, n]) => {
        const st = status[id];
        const timing = timings[id];
        const duracao =
          timing.start === null
            ? null
            : formatDuracao((timing.end ?? Date.now()) - timing.start);

        return (
          <g key={id} transform={`translate(${n.x}, ${n.y})`} className={cn(SQUISHY, NODE_TEXT_CLASS[st])}>
            <circle
              r={st === "active" ? 56 : 50}
              strokeWidth={3}
              className={cn(SQUISHY, NODE_FILL_CLASS[st], NODE_STROKE_CLASS[st], st === "active" && "node-squish")}
            />
            <g transform="translate(0, -14)">
              <NodeIcon node={id} size={30} />
            </g>
            <text textAnchor="middle" y={26} className="fill-current text-[15px] font-medium">
              {n.label}
            </text>
            {duracao && (
              <text
                textAnchor="middle"
                y={80}
                className={cn(
                  "text-[13px] font-medium tabular-nums",
                  st === "active" ? "fill-primary" : "fill-muted-foreground",
                )}
              >
                {duracao}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
