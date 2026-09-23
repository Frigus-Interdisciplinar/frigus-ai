import { useMemo, useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";

const SAUDACOES = [
  "Olá!",
  "E aí, tudo certo?",
  "Bem-vindo de volta.",
  "Oi! No que posso ajudar?",
  "Fala!",
  "Pronto pra começar?",
];

const SUBTITULOS = [
  "Pergunte sobre seu estoque, sua lista de compras, receitas ou gastos com alimentação.",
  "Posso ajudar a controlar validade, sugerir receitas ou organizar a lista de compras.",
  "Manda a pergunta que eu chamo o especialista certo.",
  "Sobre geladeira, compras, receitas ou desperdício — pode perguntar.",
];

function pick(lista: string[]): string {
  return lista[Math.floor(Math.random() * lista.length)];
}

export function EmptyState() {
  const containerRef = useRef<HTMLDivElement>(null);

  const saudacao = useMemo(() => pick(SAUDACOES), []);
  const subtitulo = useMemo(() => pick(SUBTITULOS), []);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      mm.add({ reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
        const { reduceMotion } = context.conditions as { reduceMotion: boolean };

        gsap
          .timeline({ defaults: { ease: "power3.out" } })
          .from(".empty-title", {
            autoAlpha: 0,
            y: reduceMotion ? 0 : 16,
            duration: reduceMotion ? 0 : 0.6,
          })
          .from(
            ".empty-subtitle",
            {
              autoAlpha: 0,
              y: reduceMotion ? 0 : 10,
              duration: reduceMotion ? 0 : 0.5,
            },
            "-=0.3",
          );
      });
    },
    { scope: containerRef },
  );

  return (
    <div ref={containerRef} className="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center">
      <h1 className="empty-title font-display text-3xl font-semibold text-foreground">{saudacao}</h1>
      <p className="empty-subtitle text-sm text-muted-foreground">{subtitulo}</p>
    </div>
  );
}
