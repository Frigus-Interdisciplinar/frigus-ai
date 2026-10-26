import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { cn } from "../../lib/cn";
import { FLOW_META, NODE_H, NODE_W, type Posicoes } from "../../lib/flow-meta";
import { GRAPH_EDGES } from "../../lib/graph-layout";
import type { GraphStatus, GraphTimings, GraphTools, NodeStatus } from "../../lib/use-execution-graph";
import { useTick } from "../../lib/use-tick";
import type { NodeName } from "../../types";
import { NodeIcon } from "../chat/node-icon";

interface View {
  x: number;
  y: number;
  k: number;
}

const K_MIN = 0.25;
const K_MAX = 2;
const MARGEM = 60;

const BORDA: Record<NodeStatus, string> = {
  idle: "border-border",
  active: "border-primary shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_25%,transparent)]",
  done: "border-primary/50",
};

// Volta do juiz pro especialista (reprovou): exceção, não o fluxo normal.
const ehRetentativa = (de: NodeName, para: NodeName) => de === "juiz_node" && para !== "guardrail_saida_node";

function caminho(de: { x: number; y: number }, para: { x: number; y: number }, retentativa: boolean): string {
  if (retentativa) {
    // Sai por baixo do juiz e entra por baixo do especialista, passando por fora do fluxo.
    const x1 = de.x + NODE_W / 2;
    const y1 = de.y + NODE_H;
    const x2 = para.x + NODE_W / 2;
    const y2 = para.y + NODE_H;
    const fundo = Math.max(y1, y2) + 90;
    return `M ${x1} ${y1} C ${x1} ${fundo}, ${x2} ${fundo}, ${x2} ${y2}`;
  }

  const x1 = de.x + NODE_W;
  const y1 = de.y + NODE_H / 2;
  const x2 = para.x;
  const y2 = para.y + NODE_H / 2;
  const folga = Math.max(60, Math.abs(x2 - x1) / 2);

  return `M ${x1} ${y1} C ${x1 + folga} ${y1}, ${x2 - folga} ${y2}, ${x2} ${y2}`;
}

function duracao(inicio: number | null, fim: number | null): string | null {
  if (inicio === null) return null;

  return `${(((fim ?? Date.now()) - inicio) / 1000).toFixed(1)}s`;
}

export function FlowCanvas({
  pos,
  onMove,
  status,
  timings,
  tools,
  activeEdge,
  traveled,
  selecionado,
  onSelect,
  mostrarRetentativas,
  ajustarSinal,
}: {
  pos: Posicoes;
  onMove: (id: NodeName, x: number, y: number) => void;
  status: GraphStatus;
  timings: GraphTimings;
  tools: GraphTools;
  activeEdge: string | null;
  traveled: ReadonlySet<string>;
  selecionado: NodeName | null;
  onSelect: (id: NodeName | null) => void;
  mostrarRetentativas: boolean;
  // Muda quando o pai quer reenquadrar tudo (reorganizar, botão "ajustar").
  ajustarSinal: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const posRef = useRef(pos);
  posRef.current = pos;
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 1 });
  const arraste = useRef<
    | { tipo: "pan"; sx: number; sy: number; ox: number; oy: number; moveu: boolean }
    | { tipo: "no"; id: NodeName; sx: number; sy: number; ox: number; oy: number; moveu: boolean }
    | null
  >(null);

  useTick(Object.values(status).includes("active"));

  const ajustar = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;

    const { width, height } = el.getBoundingClientRect();
    const pontos = Object.values(posRef.current);
    const minX = Math.min(...pontos.map((p) => p.x));
    const minY = Math.min(...pontos.map((p) => p.y));
    const larg = Math.max(...pontos.map((p) => p.x)) + NODE_W - minX;
    const alt = Math.max(...pontos.map((p) => p.y)) + NODE_H - minY;
    const k = Math.min((width - MARGEM * 2) / larg, (height - MARGEM * 2) / alt, 1.1);

    setView({ k, x: (width - larg * k) / 2 - minX * k, y: (height - alt * k) / 2 - minY * k });
  }, []);

  useEffect(() => {
    const id = requestAnimationFrame(ajustar);
    return () => cancelAnimationFrame(id);
  }, [ajustar, ajustarSinal]);

  const zoomEm = useCallback((fator: number, cx: number, cy: number) => {
    setView((v) => {
      const k = Math.min(K_MAX, Math.max(K_MIN, v.k * fator));
      const r = k / v.k;

      return { k, x: cx - (cx - v.x) * r, y: cy - (cy - v.y) * r };
    });
  }, []);

  // Listener nativo: o `onWheel` do React é passivo e não deixa impedir o scroll da página.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const aoRolar = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomEm(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
    };

    el.addEventListener("wheel", aoRolar, { passive: false });
    return () => el.removeEventListener("wheel", aoRolar);
  }, [zoomEm]);

  const aoPressionarFundo = (e: ReactPointerEvent) => {
    containerRef.current?.setPointerCapture(e.pointerId);
    arraste.current = { tipo: "pan", sx: e.clientX, sy: e.clientY, ox: view.x, oy: view.y, moveu: false };
  };

  const aoPressionarNo = (e: ReactPointerEvent, id: NodeName) => {
    e.stopPropagation();
    containerRef.current?.setPointerCapture(e.pointerId);
    arraste.current = { tipo: "no", id, sx: e.clientX, sy: e.clientY, ox: pos[id].x, oy: pos[id].y, moveu: false };
  };

  const aoMover = (e: ReactPointerEvent) => {
    const a = arraste.current;
    if (!a) return;

    const dx = e.clientX - a.sx;
    const dy = e.clientY - a.sy;
    if (Math.abs(dx) + Math.abs(dy) > 3) a.moveu = true;
    if (!a.moveu) return;

    if (a.tipo === "pan") setView((v) => ({ ...v, x: a.ox + dx, y: a.oy + dy }));
    else onMove(a.id, a.ox + dx / view.k, a.oy + dy / view.k);
  };

  const aoSoltar = () => {
    const a = arraste.current;
    arraste.current = null;
    if (!a || a.moveu) return;

    onSelect(a.tipo === "no" ? a.id : null);
  };

  const centro = () => {
    const r = containerRef.current?.getBoundingClientRect();
    return { x: (r?.width ?? 0) / 2, y: (r?.height ?? 0) / 2 };
  };

  return (
    <div
      ref={containerRef}
      onPointerDown={aoPressionarFundo}
      onPointerMove={aoMover}
      onPointerUp={aoSoltar}
      onPointerCancel={aoSoltar}
      className="relative h-full w-full cursor-grab touch-none select-none overflow-hidden bg-background active:cursor-grabbing"
      style={{
        backgroundImage: "radial-gradient(var(--color-border) 1px, transparent 1px)",
        backgroundSize: `${22 * view.k}px ${22 * view.k}px`,
        backgroundPosition: `${view.x}px ${view.y}px`,
      }}
    >
      <div
        className="absolute left-0 top-0"
        style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`, transformOrigin: "0 0" }}
      >
        <svg className="pointer-events-none absolute left-0 top-0 overflow-visible" width={1} height={1}>
          {GRAPH_EDGES.map(([de, para]) => {
            const retentativa = ehRetentativa(de, para);
            const chave = `${de}>${para}`;
            const acesa = activeEdge === chave;
            const percorrida = traveled.has(chave);
            const destaque = selecionado === de || selecionado === para;

            if (retentativa && !mostrarRetentativas && !acesa && !percorrida) return null;

            return (
              <path
                key={chave}
                d={caminho(pos[de], pos[para], retentativa)}
                fill="none"
                strokeLinecap="round"
                strokeWidth={acesa ? 4 : destaque ? 3 : 2}
                strokeDasharray={retentativa && !acesa ? "6 6" : undefined}
                className={cn(
                  "transition-colors duration-300",
                  acesa
                    ? "edge-flow stroke-primary"
                    : percorrida
                      ? "stroke-primary/60"
                      : destaque
                        ? "stroke-primary/40"
                        : retentativa
                          ? "stroke-muted-foreground/40"
                          : "stroke-border",
                )}
              />
            );
          })}
        </svg>

        {(Object.keys(FLOW_META) as NodeName[]).map((id) => {
          const st = status[id];
          const meta = FLOW_META[id];
          const tempo = duracao(timings[id].start, timings[id].end);

          return (
            <div
              key={id}
              onPointerDown={(e) => aoPressionarNo(e, id)}
              className={cn(
                "absolute cursor-pointer rounded-xl border-2 bg-card px-3 py-2 text-card-foreground shadow-sm transition-[border-color,box-shadow] duration-300",
                BORDA[st],
                selecionado === id && "ring-2 ring-ring",
              )}
              style={{ left: pos[id].x, top: pos[id].y, width: NODE_W, height: NODE_H }}
            >
              <span className="absolute -left-[7px] top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-border bg-card" />
              <span className="absolute -right-[7px] top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-border bg-card" />

              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                    st === "active" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
                  )}
                >
                  <svg width={22} height={22} viewBox="-11 -11 22 22">
                    <NodeIcon node={id} size={20} />
                  </svg>
                </span>
                <p className="truncate text-sm font-semibold">{meta.titulo}</p>
                {tempo && (
                  <span
                    className={cn(
                      "ml-auto text-xs font-medium tabular-nums",
                      st === "active" ? "text-primary" : "text-muted-foreground",
                    )}
                  >
                    {tempo}
                  </span>
                )}
              </div>
              <p className="mt-1.5 truncate text-xs text-muted-foreground">{meta.modelo}</p>
              {tools[id].length > 0 && (
                <div className="mt-1.5 flex gap-1 overflow-hidden">
                  {tools[id].slice(0, 3).map((t, i) => (
                    <span
                      key={`${t.nome}-${i}`}
                      className={cn(
                        "max-w-[88px] truncate rounded px-1.5 py-0.5 font-mono text-[10px]",
                        t.estado === "rodando" ? "animate-pulse bg-primary text-primary-foreground" : "bg-muted text-foreground",
                      )}
                    >
                      {t.nome}
                    </span>
                  ))}
                  {tools[id].length > 3 && (
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">+{tools[id].length - 3}</span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div
        className="absolute bottom-4 left-4 flex flex-col overflow-hidden rounded-lg border border-border bg-card text-foreground shadow-sm"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <button className="px-3 py-1.5 text-lg leading-none hover:bg-muted" aria-label="Aproximar" onClick={() => zoomEm(1.25, centro().x, centro().y)}>
          +
        </button>
        <button className="border-t border-border px-3 py-1.5 text-lg leading-none hover:bg-muted" aria-label="Afastar" onClick={() => zoomEm(0.8, centro().x, centro().y)}>
          −
        </button>
        <button className="border-t border-border px-3 py-1.5 text-xs hover:bg-muted" aria-label="Ajustar à tela" onClick={ajustar}>
          ajustar
        </button>
      </div>
    </div>
  );
}
