import type { ReactElement } from "react";
import type { NodeName } from "../../types";

// Ícones minimalistas (stroke = currentColor, herda a cor do <g> pai) — cada node do grafo tem
// uma identidade visual própria em vez de todos usarem o mesmo glifo genérico.
const ICON_PATHS: Record<NodeName, ReactElement> = {
  guardrail_entrada_node: (
    <path d="M12 2 L4 5 V11 C4 16.5 7.5 20.5 12 22 C16.5 20.5 20 16.5 20 11 V5 Z" />
  ),
  guardrail_saida_node: (
    <path d="M12 2 L4 5 V11 C4 16.5 7.5 20.5 12 22 C16.5 20.5 20 16.5 20 11 V5 Z" />
  ),
  roteador_node: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M15 9 L11 13 L9 15 L13 11 Z" fill="currentColor" stroke="none" />
    </>
  ),
  financeiro_node: (
    <>
      <path d="M12 3 V21" />
      <path d="M16.5 7.5 C16.5 5.8 14.6 4.5 12 4.5 C9.4 4.5 7.8 5.8 7.8 7.6 C7.8 9.8 10 10.3 12 10.8 C14.4 11.4 16.2 12.1 16.2 14.4 C16.2 16.3 14.4 17.6 12 17.6 C9.6 17.6 7.5 16.3 7.5 14.5" />
    </>
  ),
  faq_node: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.3 9.4 C9.3 7.7 10.6 6.5 12.2 6.5 C13.8 6.5 15 7.6 15 9.1 C15 10.8 13.1 11.3 12.3 12.6 C12.1 12.9 12 13.3 12 13.7" />
      <circle cx="12" cy="16.6" r="0.95" fill="currentColor" stroke="none" />
    </>
  ),
  orquestrador_node: (
    <>
      <circle cx="12" cy="5.5" r="2.1" />
      <circle cx="5.5" cy="18" r="2.1" />
      <circle cx="18.5" cy="18" r="2.1" />
      <path d="M12 7.6 V12 M12 12 L6.7 16.2 M12 12 L17.3 16.2" />
    </>
  ),
  // Geladeira: corpo + prateleira — estoque é sobre o que já está guardado.
  estoque_node: (
    <>
      <rect x="5" y="2.5" width="14" height="19" rx="1.5" />
      <path d="M5 10 H19" />
      <path d="M8 4.5 V8 M8 12 V15" />
    </>
  ),
  // Sacola de compras.
  compras_node: (
    <>
      <path d="M6 8 H18 L17 21 H7 Z" />
      <path d="M9 8 V6.5 C9 4.5 10.3 3 12 3 C13.7 3 15 4.5 15 6.5 V8" />
    </>
  ),
  // Panela com "vapor" — receitas/cozinha.
  receitas_node: (
    <>
      <path d="M4 11 H20 C20 15.5 16.5 20 12 20 C7.5 20 4 15.5 4 11 Z" />
      <path d="M2 11 H4 M20 11 H22" />
      <path d="M9 8 V4 M12 8 V3 M15 8 V4" />
    </>
  ),
  // Olho — visão computacional (foto da geladeira).
  visao_node: (
    <>
      <path d="M2 12 C4.5 6.5 8 4.5 12 4.5 C16 4.5 19.5 6.5 22 12 C19.5 17.5 16 19.5 12 19.5 C8 19.5 4.5 17.5 2 12 Z" />
      <circle cx="12" cy="12" r="3.2" />
    </>
  ),
  // Balança — juiz (LLM-as-judge).
  juiz_node: (
    <>
      <path d="M12 3 V19" />
      <path d="M5 19 H19" />
      <path d="M12 6.5 L4.5 10" />
      <path d="M12 6.5 L19.5 10" />
      <path d="M1.8 10 C1.8 12.8 3.5 14.5 5 14.5 C6.5 14.5 8.2 12.8 8.2 10 Z" />
      <path d="M15.8 10 C15.8 12.8 17.5 14.5 19 14.5 C20.5 14.5 22.2 12.8 22.2 10 Z" />
    </>
  ),
};

export function NodeIcon({ node, size = 24 }: { node: NodeName; size?: number }) {
  return (
    <g transform={`translate(${-size / 2}, ${-size / 2})`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {ICON_PATHS[node]}
      </svg>
    </g>
  );
}
