import { useCallback, useRef, useState } from "react";
import type { ExecutionEvent, NodeName } from "../types";

export type NodeStatus = "idle" | "active" | "done";
export type GraphStatus = Record<NodeName, NodeStatus>;
export type NodeTiming = { start: number | null; end: number | null };
export type GraphTimings = Record<NodeName, NodeTiming>;

const NODES: NodeName[] = [
  "guardrail_entrada_node",
  "roteador_node",
  "estoque_node",
  "compras_node",
  "receitas_node",
  "faq_node",
  "financeiro_node",
  "a2a_assessor_node",
  "visao_node",
  "orquestrador_node",
  "juiz_node",
  "guardrail_saida_node",
];

function idleStatus(): GraphStatus {
  return Object.fromEntries(NODES.map((n) => [n, "idle"])) as GraphStatus;
}

function idleTimings(): GraphTimings {
  return Object.fromEntries(NODES.map((n) => [n, { start: null, end: null }])) as GraphTimings;
}

// Consome a timeline de execução (SSE) e mantém o estado visual do grafo: qual node está ativo,
// quais já terminaram, qual aresta acabou de ser percorrida, quais já foram (`traveled`, as
// arestas de fato usadas — não "toda saída de um nó que rodou") e quanto tempo cada node levou.
export function useExecutionGraph() {
  const [status, setStatus] = useState<GraphStatus>(idleStatus);
  const [timings, setTimings] = useState<GraphTimings>(idleTimings);
  const [activeEdge, setActiveEdge] = useState<string | null>(null);
  const [traveled, setTraveled] = useState<ReadonlySet<string>>(() => new Set());
  const lastNode = useRef<NodeName | null>(null);

  const feed = useCallback((evento: ExecutionEvent) => {
    switch (evento.type) {
      case "run_started":
        lastNode.current = null;
        setStatus(idleStatus());
        setTimings(idleTimings());
        setActiveEdge(null);
        setTraveled(new Set());
        break;

      case "node_started": {
        const agora = Date.now();

        setStatus((prev) => {
          const next = { ...prev };
          if (lastNode.current) next[lastNode.current] = "done";
          next[evento.node] = "active";
          return next;
        });
        setTimings((prev) => {
          const next = { ...prev };
          if (lastNode.current && next[lastNode.current].end === null) {
            next[lastNode.current] = { ...next[lastNode.current], end: agora };
          }
          next[evento.node] = { start: agora, end: null };
          return next;
        });
        const aresta = lastNode.current ? `${lastNode.current}>${evento.node}` : null;
        setActiveEdge(aresta);
        if (aresta) setTraveled((prev) => new Set(prev).add(aresta));
        lastNode.current = evento.node;
        break;
      }

      case "node_finished":
        setStatus((prev) => ({ ...prev, [evento.node]: "done" }));
        setTimings((prev) => ({
          ...prev,
          [evento.node]: { ...prev[evento.node], end: prev[evento.node].end ?? Date.now() },
        }));
        break;

      case "run_finished":
      case "run_failed": {
        const node = lastNode.current;
        if (node) {
          setStatus((prev) => ({ ...prev, [node]: "done" }));
          setTimings((prev) => ({
            ...prev,
            [node]: { ...prev[node], end: prev[node].end ?? Date.now() },
          }));
        }
        setActiveEdge(null);
        break;
      }
    }
  }, []);

  const reset = useCallback(() => {
    lastNode.current = null;
    setStatus(idleStatus());
    setTimings(idleTimings());
    setActiveEdge(null);
    setTraveled(new Set());
  }, []);

  return { status, timings, activeEdge, traveled, feed, reset };
}
