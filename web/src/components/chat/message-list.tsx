import { useEffect, useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { Message } from "../../types";
import { EmptyState } from "./empty-state";
import { MessageBubble } from "./message-bubble";
import { ThinkingBubble } from "./thinking-bubble";

export function MessageList({
  messages,
  pensando,
}: {
  messages: Message[];
  pensando: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      mm.add({ reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
        const { reduceMotion } = context.conditions as { reduceMotion: boolean };
        const nodes = containerRef.current?.querySelectorAll(".message-item");
        const last = nodes?.[nodes.length - 1];
        if (!last) return;

        gsap.from(last, {
          autoAlpha: 0,
          y: 12,
          scale: 0.98,
          duration: reduceMotion ? 0 : 0.35,
          ease: "power2.out",
        });
      });
    },
    { scope: containerRef, dependencies: [messages.length] },
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, pensando]);

  if (messages.length === 0 && !pensando) {
    return <EmptyState />;
  }

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full max-w-2xl flex-col gap-2 px-4 py-6">
        {/* empurra as mensagens pra baixo (perto do input) quando tem poucas; some ao rolar */}
        <div className="flex-1" />
        {messages.map((message, i) => (
          <div key={i} className="message-item">
            <MessageBubble message={message} />
          </div>
        ))}
        {pensando && <ThinkingBubble />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
