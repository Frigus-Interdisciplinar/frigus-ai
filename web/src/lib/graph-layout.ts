import type { NodeName } from "../types";

// Estoque/compras/financeiro/visão passam pelo orquestrador (JSON -> linguagem natural);
// receitas/faq/assessor já respondem em linguagem natural e vão direto pro juiz — o assessor
// (A2A) pula o juiz e vai pra saída quando está fora do ar (`decidir_apos_assessor`). O juiz pode
// aprovar (-> guardrail de saída) ou reprovar e devolver pro MESMO especialista que originou a
// resposta (uma aresta de volta por especialista, visão inclusa) — ver `decidir_apos_juiz`.
export const GRAPH_EDGES: [NodeName, NodeName][] = [
  ["guardrail_entrada_node", "roteador_node"],
  ["guardrail_entrada_node", "visao_node"],
  ["roteador_node", "estoque_node"],
  ["roteador_node", "compras_node"],
  ["roteador_node", "receitas_node"],
  ["roteador_node", "faq_node"],
  ["roteador_node", "financeiro_node"],
  ["roteador_node", "a2a_assessor_node"],
  ["estoque_node", "orquestrador_node"],
  ["compras_node", "orquestrador_node"],
  ["financeiro_node", "orquestrador_node"],
  ["visao_node", "orquestrador_node"],
  ["receitas_node", "juiz_node"],
  ["faq_node", "juiz_node"],
  ["a2a_assessor_node", "juiz_node"],
  ["a2a_assessor_node", "guardrail_saida_node"],
  ["orquestrador_node", "juiz_node"],
  ["juiz_node", "guardrail_saida_node"],
  ["juiz_node", "estoque_node"],
  ["juiz_node", "compras_node"],
  ["juiz_node", "receitas_node"],
  ["juiz_node", "faq_node"],
  ["juiz_node", "financeiro_node"],
  ["juiz_node", "a2a_assessor_node"],
  ["juiz_node", "visao_node"],
];
