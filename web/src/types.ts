export interface ChatSummary {
  chat_id: string;
  resume: string;
  updated_at: string;
}

export type Role = "user" | "assistant";

export interface Message {
  role: Role;
  content: string;
}

export type NodeName =
  | "guardrail_entrada_node"
  | "roteador_node"
  | "estoque_node"
  | "compras_node"
  | "receitas_node"
  | "faq_node"
  | "financeiro_node"
  | "a2a_assessor_node"
  | "visao_node"
  | "orquestrador_node"
  | "juiz_node"
  | "guardrail_saida_node";

export type Route =
  | "estoque"
  | "compras"
  | "receitas"
  | "faq"
  | "financeiro"
  | "assessor"
  | "fim"
  | "visao"
  | "guardrail_entrada"
  | "guardrail_saida"
  | "juiz";

export type ExecutionEvent =
  | { type: "run_started" }
  | { type: "node_started"; node: NodeName }
  | { type: "route_selected"; route: Route }
  | { type: "node_finished"; node: NodeName }
  | { type: "answer_ready"; content: string }
  | { type: "run_finished" }
  | { type: "run_failed"; message: string };

// Espelha `Fatos` (schemas/models.py) — coleção `user_fatos`, GET/PUT /profile.
export interface Fatos {
  alergias: string[];
  preferencias: string[];
  restricoes: string[];
  habitos: string[];
}
