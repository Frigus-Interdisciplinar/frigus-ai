import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ChatInput } from "../components/chat/chat-input";
import { MessageList } from "../components/chat/message-list";
import { FlowCanvas } from "../components/canvas/flow-canvas";
import { Sidebar } from "../components/sidebar/sidebar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { createChat, getMessages, streamMessage } from "../lib/api";
import { getMetricsToken } from "../lib/auth";
import { cn } from "../lib/cn";
import { FLOW_META, POSICOES_PADRAO, type Posicoes } from "../lib/flow-meta";
import { groupByLabel, histogramStatsByLabel, parseMetrics, type PromSample } from "../lib/prom";
import { useExecutionGraph } from "../lib/use-execution-graph";
import type { Message, NodeName } from "../types";

const CHAVE_POSICOES = "frigus_canvas_posicoes";

function lerPosicoes(): Posicoes {
  try {
    const salvo = localStorage.getItem(CHAVE_POSICOES);
    if (salvo) return { ...POSICOES_PADRAO, ...JSON.parse(salvo) };
  } catch {
    // storage indisponível ou JSON antigo: volta pro layout padrão
  }

  return POSICOES_PADRAO;
}

function fmt(s: number): string {
  return s < 10 ? `${s.toFixed(2)}s` : `${s.toFixed(1)}s`;
}

// Tela principal: o canvas do agente + as sessões à esquerda + a conversa à direita. Rodar uma
// mensagem aqui acende os nós e as tools no canvas enquanto a resposta é construída.
export function ChatPage() {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const graph = useExecutionGraph();

  const [messages, setMessages] = useState<Message[]>([]);
  const [pensando, setPensando] = useState(false);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);

  const [pos, setPos] = useState<Posicoes>(lerPosicoes);
  const [selecionado, setSelecionado] = useState<NodeName | null>(null);
  const [retentativas, setRetentativas] = useState(false);
  const [ajustarSinal, setAjustarSinal] = useState(0);
  const [samples, setSamples] = useState<PromSample[] | null>(null);

  // Evita que o refetch disparado por navigate() (logo abaixo de createChat) sobrescreva as
  // mensagens otimistas já em tela antes da resposta chegar e ser persistida.
  const skipNextFetchRef = useRef(false);
  // Chat que está de fato em tela agora: trocar de conversa com uma resposta a caminho não pode
  // grudar a resposta antiga na conversa nova.
  const activeChatIdRef = useRef(chatId);

  useEffect(() => {
    activeChatIdRef.current = chatId;
    graph.reset();

    if (skipNextFetchRef.current) {
      skipNextFetchRef.current = false;
      return;
    }

    if (!chatId) {
      setMessages([]);
      return;
    }

    // Um fetch mais antigo que resolve depois de um mais novo não pode sobrescrever as mensagens
    // certas com as do chat errado.
    let cancelado = false;

    getMessages(chatId)
      .then((msgs) => {
        if (!cancelado) setMessages(msgs);
      })
      .catch(() => {
        if (!cancelado) setMessages([]);
      });

    return () => {
      cancelado = true;
    };
    // `graph.reset` é estável (useCallback); não entra pra não refazer o fetch a cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId]);

  useEffect(() => {
    try {
      localStorage.setItem(CHAVE_POSICOES, JSON.stringify(pos));
    } catch {
      // sem storage: o layout vale só até recarregar
    }
  }, [pos]);

  // Métricas reais por nó pro inspetor. O /metrics pode pedir o token do Prometheus; sem ele o
  // inspetor só omite os números.
  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      try {
        const token = getMetricsToken();
        const res = await fetch("/metrics", { headers: token ? { Authorization: `Bearer ${token}` } : {} });
        if (res.ok && !cancelado) setSamples(parseMetrics(await res.text()));
      } catch {
        // inspetor segue sem métricas
      }
    }

    carregar();
    const id = setInterval(carregar, 15_000);
    return () => {
      cancelado = true;
      clearInterval(id);
    };
  }, []);

  const mover = useCallback((id: NodeName, x: number, y: number) => {
    setPos((p) => ({ ...p, [id]: { x, y } }));
  }, []);

  const reorganizar = () => {
    setPos(POSICOES_PADRAO);
    setAjustarSinal((n) => n + 1);
  };

  const handleSend = useCallback(
    async (content: string) => {
      let id = chatId;

      setMessages((prev) => [...prev, { role: "user", content }]);
      setPensando(true);
      graph.reset();

      try {
        if (!id) {
          const created = await createChat();
          id = created.chat_id;
          activeChatIdRef.current = id;
          skipNextFetchRef.current = true;
          setSidebarRefresh((n) => n + 1);
          navigate(`/chat/${id}`, { replace: true });
        }

        let resposta: string | null = null;
        let falha: string | null = null;

        await streamMessage(id, content, (evento) => {
          if (activeChatIdRef.current !== id) return;

          graph.feed(evento);

          if (evento.type === "answer_ready") resposta = evento.content;
          if (evento.type === "run_failed") falha = evento.message;
        });

        if (activeChatIdRef.current !== id) return;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: resposta ?? falha ?? "Erro ao enviar mensagem." },
        ]);
        setSidebarRefresh((n) => n + 1);
      } catch (err) {
        if (activeChatIdRef.current !== id) return;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: err instanceof Error ? err.message : "Erro ao enviar mensagem." },
        ]);
      } finally {
        setPensando(false);
      }
    },
    // `graph.feed`/`graph.reset` são estáveis (useCallback).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [chatId, navigate],
  );

  const meta = selecionado ? FLOW_META[selecionado] : null;
  const execs = selecionado && samples ? (groupByLabel(samples, "frigus_node_runs_total", "node")[selecionado] ?? 0) : null;
  const tempos = samples ? histogramStatsByLabel(samples, "frigus_node_duration_seconds", "node") : null;
  const tempoNo = selecionado && tempos ? tempos[selecionado] : null;
  const statusNo = selecionado ? graph.status[selecionado] : null;

  return (
    <div className="flex h-screen">
      <Sidebar refreshKey={sidebarRefresh} />

      <div className="relative min-w-0 flex-1">
        <FlowCanvas
          pos={pos}
          onMove={mover}
          status={graph.status}
          timings={graph.timings}
          tools={graph.tools}
          activeEdge={graph.activeEdge}
          traveled={graph.traveled}
          selecionado={selecionado}
          onSelect={setSelecionado}
          mostrarRetentativas={retentativas}
          ajustarSinal={ajustarSinal}
        />

        <div className="absolute left-4 top-4 flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
          <span className="font-display text-sm font-semibold text-foreground">Fluxo do agente</span>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={retentativas} onChange={(e) => setRetentativas(e.target.checked)} />
            retentativas do juiz
          </label>
          <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={reorganizar}>
            reorganizar
          </Button>
        </div>

        {meta && selecionado && (
          <Card className="absolute right-4 top-4 flex max-h-[calc(100%-2rem)] w-80 flex-col gap-3 overflow-y-auto p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-display text-base font-semibold text-foreground">{meta.titulo}</p>
                <p className="text-xs text-muted-foreground">{selecionado}</p>
              </div>
              <button className="text-muted-foreground hover:text-foreground" aria-label="Fechar" onClick={() => setSelecionado(null)}>
                ×
              </button>
            </div>

            <p className="text-sm text-foreground">{meta.descricao}</p>

            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">modelo</p>
              <p className="text-sm text-foreground">{meta.modelo}</p>
            </div>

            {meta.tools.length > 0 && (
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">ferramentas</p>
                <div className="flex flex-wrap gap-1">
                  {meta.tools.map((t) => {
                    const usada = graph.tools[selecionado].some((u) => u.nome === t);

                    return (
                      <code
                        key={t}
                        className={cn(
                          "rounded px-1.5 py-0.5 text-xs",
                          usada ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
                        )}
                      >
                        {t}
                      </code>
                    );
                  })}
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">em destaque: chamadas neste turno</p>
              </div>
            )}

            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">desde que a API subiu</p>
              {execs === null || !tempoNo ? (
                <p className="text-sm text-muted-foreground">sem métricas (o /metrics pode pedir o token, veja a tela de Métricas)</p>
              ) : (
                <div className="grid grid-cols-3 gap-2 text-center">
                  <Stat rotulo="execuções" valor={String(Math.round(execs))} />
                  <Stat rotulo="tempo médio" valor={tempoNo.count > 0 ? fmt(tempoNo.avgSeconds) : "-"} />
                  <Stat rotulo="tempo total" valor={fmt(tempoNo.totalSeconds)} />
                </div>
              )}
            </div>

            {statusNo && statusNo !== "idle" && (
              <p className="text-xs text-muted-foreground">
                nesta execução:{" "}
                <span className="font-medium text-foreground">{statusNo === "active" ? "em andamento" : "concluído"}</span>
              </p>
            )}
          </Card>
        )}
      </div>

      <aside className="flex h-screen w-[400px] shrink-0 flex-col border-l border-border bg-card">
        <p className="border-b border-border px-4 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          conversa
        </p>
        <MessageList messages={messages} pensando={pensando} />
        <ChatInput onSend={handleSend} disabled={pensando} />
      </aside>
    </div>
  );
}

function Stat({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="rounded-md bg-muted px-2 py-1.5">
      <p className="text-sm font-semibold tabular-nums text-foreground">{valor}</p>
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{rotulo}</p>
    </div>
  );
}
