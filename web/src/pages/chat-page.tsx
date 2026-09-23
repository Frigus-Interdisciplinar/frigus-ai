import { useCallback, useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useNavigate, useParams } from "react-router";
import { createChat, getMessages, streamMessage } from "../lib/api";
import { ChatInput } from "../components/chat/chat-input";
import { GraphPanel } from "../components/chat/graph-panel";
import { MessageList } from "../components/chat/message-list";
import { Sidebar } from "../components/sidebar/sidebar";
import { useExecutionGraph } from "../lib/use-execution-graph";
import type { Message } from "../types";

export function ChatPage() {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [pensando, setPensando] = useState(false);
  const graph = useExecutionGraph();
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const mainRef = useRef<HTMLDivElement>(null);
  // Evita que o refetch disparado por navigate() (logo abaixo de createChat) sobrescreva as
  // mensagens otimistas já em tela antes da resposta do Assessor chegar e ser persistida.
  const skipNextFetchRef = useRef(false);
  // Chat que está de fato em tela agora. handleSend guarda o resultado de sendMessage contra
  // isso antes de aplicar em setMessages — sem essa checagem, trocar de conversa (sidebar ou
  // "Nova conversa") enquanto uma resposta ainda está a caminho faz a resposta da conversa
  // antiga aparecer grudada na conversa nova/diferente que está em tela quando ela chega.
  const activeChatIdRef = useRef(chatId);

  useEffect(() => {
    activeChatIdRef.current = chatId;

    if (skipNextFetchRef.current) {
      skipNextFetchRef.current = false;
      return;
    }

    if (!chatId) {
      setMessages([]);
      return;
    }

    // Cancela aplicar o resultado se o efeito rodar de novo antes de resolver (troca rápida
    // entre chats na sidebar) — sem isso, um fetch mais antigo que resolve depois de um mais
    // novo sobrescreve as mensagens certas com as do chat errado.
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
  }, [chatId]);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      mm.add({ reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
        const { reduceMotion } = context.conditions as { reduceMotion: boolean };

        gsap.from(mainRef.current, {
          autoAlpha: 0,
          duration: reduceMotion ? 0 : 0.3,
          ease: "power2.out",
        });
      });
    },
    { scope: mainRef },
  );

  const handleSend = useCallback(
    async (content: string) => {
      let id = chatId;

      setMessages((prev) => [...prev, { role: "user", content }]);
      setPensando(true);

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
          {
            role: "assistant",
            content: err instanceof Error ? err.message : "Erro ao enviar mensagem.",
          },
        ]);
      } finally {
        setPensando(false);
      }
    },
    [chatId, navigate],
  );

  return (
    <div className="flex h-screen">
      <Sidebar refreshKey={sidebarRefresh} />
      <div ref={mainRef} className="flex flex-1 flex-col">
        <MessageList messages={messages} pensando={pensando} />
        <ChatInput onSend={handleSend} disabled={pensando} />
      </div>
      <GraphPanel status={graph.status} timings={graph.timings} activeEdge={graph.activeEdge} />
    </div>
  );
}
