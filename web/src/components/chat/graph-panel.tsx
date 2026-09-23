import type { GraphStatus, GraphTimings } from "../../lib/use-execution-graph";
import { GraphView } from "./graph-view";

export function GraphPanel({
  status,
  timings,
  activeEdge,
}: {
  status: GraphStatus;
  timings: GraphTimings;
  activeEdge: string | null;
}) {
  return (
    <aside className="hidden h-screen w-[760px] shrink-0 flex-col justify-center border-l border-border bg-card p-6 xl:flex">
      <p className="mb-4 text-center text-xs font-medium uppercase tracking-wide text-muted-foreground">
        execução do agente
      </p>
      <div
        className="flex flex-1 items-center justify-center rounded-xl border border-border bg-background bg-[radial-gradient(var(--color-border)_1px,transparent_1px)] bg-[length:22px_22px] p-6"
      >
        <GraphView status={status} timings={timings} activeEdge={activeEdge} />
      </div>
    </aside>
  );
}
