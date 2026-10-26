import type { NodeName } from "../types";

// Tamanho do card de cada nó no canvas (em unidades do canvas, antes do zoom).
export const NODE_W = 230;
export const NODE_H = 104;

export interface FlowNodeMeta {
  titulo: string;
  descricao: string;
  modelo: string;
  tools: string[];
}

// Espelha o que está em graph/builder.py, graph/agents.py e graph/llm.py. Mesmo critério de
// graph-layout.ts: a topologia não sai do backend, e muda raramente o bastante pra valer hardcodear.
export const FLOW_META: Record<NodeName, FlowNodeMeta> = {
  guardrail_entrada_node: {
    titulo: "Guardrail de entrada",
    descricao: "Barra injeção de prompt e acesso interno, e anonimiza dados pessoais antes de qualquer outro passo.",
    modelo: "regras + JeV (reserva: Luna, Groq)",
    tools: [],
  },
  roteador_node: {
    titulo: "Roteador",
    descricao: "Escolhe quais especialistas atendem o pedido (um ou vários em paralelo).",
    modelo: "JeV (reserva: Luna, Groq)",
    tools: [],
  },
  visao_node: {
    titulo: "Visão",
    descricao: "Lê a foto da geladeira e lista o que reconhece. Não grava no estoque: o usuário confirma antes.",
    modelo: "Luna (visão)",
    tools: [],
  },
  estoque_node: {
    titulo: "Estoque",
    descricao: "Consulta e altera o estoque do usuário (produtos, quantidades, validade, descarte).",
    modelo: "Luna",
    tools: ["query_stock", "add_stock_product", "add_stock_products", "update_stock_quantity", "discard_product"],
  },
  compras_node: {
    titulo: "Compras",
    descricao: "Mantém a lista de compras e dá entrada no estoque quando algo é comprado.",
    modelo: "Luna",
    tools: [
      "query_shopping_list",
      "add_shopping_list_product",
      "create_shopping_list",
      "generate_shopping_list_from_low_stock",
      "mark_purchased",
      "register_purchase",
    ],
  },
  receitas_node: {
    titulo: "Receitas",
    descricao: "Sugere receitas pelo que há no estoque, respeitando alergias, e detalha o preparo.",
    modelo: "Luna",
    tools: [
      "match_recipes_to_stock",
      "get_recipe_details",
      "sugerir_receitas_compativeis",
      "find_recipes_by_ingredients",
      "get_recipe_information",
    ],
  },
  faq_node: {
    titulo: "FAQ",
    descricao: "Responde dúvidas sobre o Frigus com RAG sobre a documentação (Qdrant).",
    modelo: "Luna",
    tools: ["faq_retriever"],
  },
  financeiro_node: {
    titulo: "Financeiro",
    descricao: "Gastos, desperdício e comparações mensais a partir do histórico de estoque.",
    modelo: "Luna",
    tools: ["gastos_mensais", "comparacao_mensal", "evolucao_desperdicio", "ranking_desperdicio", "valor_descartado"],
  },
  a2a_assessor_node: {
    titulo: "Assessor (A2A)",
    descricao: "Pergunta ao Assessor financeiro externo por A2A. Se estiver fora do ar, o fluxo segue sem ele.",
    modelo: "agente externo",
    tools: [],
  },
  orquestrador_node: {
    titulo: "Orquestrador",
    descricao: "Junta os resultados dos especialistas em uma única resposta em linguagem natural.",
    modelo: "Luna",
    tools: [],
  },
  juiz_node: {
    titulo: "Juiz",
    descricao:
      "Confere se a resposta é sustentada pelos dados, relevante e completa. Se reprovar, devolve ao especialista (até 2 reescritas).",
    modelo: "JeV (reserva: Luna, Groq)",
    tools: [],
  },
  guardrail_saida_node: {
    titulo: "Guardrail de saída",
    descricao: "Última revisão de compliance e dados pessoais antes de entregar a resposta.",
    modelo: "regras + Luna",
    tools: [],
  },
};

// Colunas da esquerda pra direita (estilo Langflow): entrada → roteamento → especialistas →
// orquestrador → juiz → saída.
const COL = 330;
const ROW = 112;

export const POSICOES_PADRAO: Record<NodeName, { x: number; y: number }> = {
  guardrail_entrada_node: { x: 0, y: ROW * 2.4 },
  roteador_node: { x: COL, y: ROW * 1.4 },
  visao_node: { x: COL, y: ROW * 4 },
  estoque_node: { x: COL * 2, y: 0 },
  compras_node: { x: COL * 2, y: ROW },
  receitas_node: { x: COL * 2, y: ROW * 2 },
  faq_node: { x: COL * 2, y: ROW * 3 },
  financeiro_node: { x: COL * 2, y: ROW * 4 },
  a2a_assessor_node: { x: COL * 2, y: ROW * 5 },
  orquestrador_node: { x: COL * 3, y: ROW * 1.6 },
  juiz_node: { x: COL * 4, y: ROW * 2.6 },
  guardrail_saida_node: { x: COL * 5, y: ROW * 2.6 },
};

export type Posicoes = Record<NodeName, { x: number; y: number }>;
