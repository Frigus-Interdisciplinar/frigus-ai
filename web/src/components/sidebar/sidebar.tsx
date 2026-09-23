import { useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Link, useNavigate, useParams } from "react-router";
import { listChats } from "../../lib/api";
import type { ChatSummary } from "../../types";
import { Button } from "../ui/button";

export function Sidebar({ refreshKey }: { refreshKey: number }) {
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { chatId } = useParams();

  useEffect(() => {
    listChats()
      .then(setChats)
      .catch(() => setChats([]));
  }, [refreshKey]);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      mm.add({ reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
        const { reduceMotion } = context.conditions as { reduceMotion: boolean };

        gsap.from(".chat-list-item", {
          autoAlpha: 0,
          y: 8,
          stagger: reduceMotion ? 0 : 0.04,
          duration: reduceMotion ? 0 : 0.3,
          ease: "power2.out",
        });
      });
    },
    { scope: containerRef, dependencies: [chats.length] },
  );

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-2 px-4 pb-2 pt-4">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary font-display text-sm font-bold text-primary-foreground">
          F
        </span>
        <span className="font-display text-sm font-semibold tracking-wide">Frigus.AI</span>
      </div>

      <div className="p-3">
        <Button className="w-full justify-center gap-1.5" onClick={() => navigate("/chat")}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.2}
            strokeLinecap="round"
          >
            <path d="M12 5 V19" />
            <path d="M5 12 H19" />
          </svg>
          Nova conversa
        </Button>
      </div>

      <p className="px-4 pb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        conversas
      </p>

      <div ref={containerRef} className="flex-1 overflow-y-auto px-2">
        {chats.map((chat) => (
          <button
            key={chat.chat_id}
            onClick={() => navigate(`/chat/${chat.chat_id}`)}
            className={`chat-list-item flex w-full items-center gap-2 truncate rounded-md px-3 py-2 text-left text-sm hover:bg-accent/10 ${
              chat.chat_id === chatId ? "bg-accent/15 font-medium" : ""
            }`}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.8}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="shrink-0 text-muted-foreground"
            >
              <path d="M4 5 H20 V16 H9 L5 19.5 V16 H4 Z" />
            </svg>
            <span className="truncate">{chat.resume || "Nova conversa"}</span>
          </button>
        ))}
      </div>

      <div className="border-t border-sidebar-border p-3">
        <Link
          to="/perfil"
          className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent/10"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="shrink-0"
          >
            <path d="M12 3 V21" />
            <path d="M16.5 7.5 C16.5 5.8 14.6 4.5 12 4.5 C9.4 4.5 7.8 5.8 7.8 7.6 C7.8 9.8 10 10.3 12 10.8 C14.4 11.4 16.2 12.1 16.2 14.4 C16.2 16.3 14.4 17.6 12 17.6 C9.6 17.6 7.5 16.3 7.5 14.5" />
          </svg>
          Perfil alimentar
        </Link>
        <Link
          to="/metrics"
          className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent/10"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="shrink-0"
          >
            <path d="M4 20 V4" />
            <path d="M9 20 V10" />
            <path d="M14 20 V13" />
            <path d="M19 20 V7" />
          </svg>
          Métricas
        </Link>
      </div>
    </aside>
  );
}
