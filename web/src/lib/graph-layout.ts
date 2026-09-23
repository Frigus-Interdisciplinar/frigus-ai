import type { NodeName } from "../types";

// Layout fixo espelhando o grafo em graph/builder.py — não dá pra derivar isso do backend sem
// expor a topologia via API, e ela muda raramente o bastante pra valer hardcodear.
export const NODE_META: Record<NodeName, { x: number; y: number; label: string }> = {
  guardrail_entrada_node: { x: 500, y: 60, label: "entrada" },
  roteador_node: { x: 380, y: 200, label: "roteador" },
  visao_node: { x: 720, y: 200, label: "visão" },
  estoque_node: { x: 80, y: 380, label: "estoque" },
  compras_node: { x: 280, y: 380, label: "compras" },
  receitas_node: { x: 480, y: 380, label: "receitas" },
  faq_node: { x: 680, y: 380, label: "faq" },
  financeiro_node: { x: 880, y: 380, label: "financeiro" },
  orquestrador_node: { x: 300, y: 560, label: "orquestrador" },
  juiz_node: { x: 500, y: 720, label: "juiz" },
  guardrail_saida_node: { x: 500, y: 860, label: "saída" },
};

// Estoque/compras/financeiro/visão passam pelo orquestrador (JSON -> linguagem natural);
// receitas/faq já respondem em linguagem natural e vão direto pro juiz. O juiz pode aprovar
// (-> guardrail de saída) ou reprovar e devolver pro MESMO especialista que originou a
// resposta (uma aresta de volta por especialista) — ver `decidir_apos_juiz` em builder.py.
export const GRAPH_EDGES: [NodeName, NodeName][] = [
  ["guardrail_entrada_node", "roteador_node"],
  ["guardrail_entrada_node", "visao_node"],
  ["roteador_node", "estoque_node"],
  ["roteador_node", "compras_node"],
  ["roteador_node", "receitas_node"],
  ["roteador_node", "faq_node"],
  ["roteador_node", "financeiro_node"],
  ["estoque_node", "orquestrador_node"],
  ["compras_node", "orquestrador_node"],
  ["financeiro_node", "orquestrador_node"],
  ["visao_node", "orquestrador_node"],
  ["receitas_node", "juiz_node"],
  ["faq_node", "juiz_node"],
  ["orquestrador_node", "juiz_node"],
  ["juiz_node", "guardrail_saida_node"],
  ["juiz_node", "estoque_node"],
  ["juiz_node", "compras_node"],
  ["juiz_node", "receitas_node"],
  ["juiz_node", "faq_node"],
  ["juiz_node", "financeiro_node"],
];

export const VIEWBOX = "0 0 1000 920";
