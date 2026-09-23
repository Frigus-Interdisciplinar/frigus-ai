"""
Eventos da timeline de execução do agente, pra streaming via SSE
(`POST /chats/{chat_id}/messages/stream`, ver `api/routes/chats.py`).

Nunca carregam prompt, estado interno do grafo, argumento de tool ou conteúdo cru de LLM — só
identidade de node e a resposta final já revisada. Quem produz esses eventos é
`services/runner.py:executar_stream`.

Sem streaming de token da resposta final: o texto só fica seguro pra mostrar depois que o nó que
respondeu (guardrail_saida, ou o roteador/guardrail de entrada respondendo direto) processou o
texto inteiro — guardrail e redação de PII operam sobre o texto completo, não em fragmentos.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from frigus_ai.graph.names import NodeLiteral
from frigus_ai.graph.state import RouteLiteral


class RunStarted(BaseModel):
    type: Literal["run_started"] = "run_started"


class NodeStarted(BaseModel):
    type: Literal["node_started"] = "node_started"
    node: NodeLiteral


class RouteSelected(BaseModel):
    type: Literal["route_selected"] = "route_selected"
    route: RouteLiteral


class NodeFinished(BaseModel):
    type: Literal["node_finished"] = "node_finished"
    node: NodeLiteral


class AnswerReady(BaseModel):
    type: Literal["answer_ready"] = "answer_ready"
    content: str


class RunFinished(BaseModel):
    type: Literal["run_finished"] = "run_finished"


class RunFailed(BaseModel):
    type: Literal["run_failed"] = "run_failed"
    message: str


ExecutionEvent = Annotated[
    RunStarted
    | NodeStarted
    | RouteSelected
    | NodeFinished
    | AnswerReady
    | RunFinished
    | RunFailed,
    Field(discriminator="type"),
]


__all__ = [
    "AnswerReady",
    "ExecutionEvent",
    "NodeFinished",
    "NodeStarted",
    "RouteSelected",
    "RunFailed",
    "RunFinished",
    "RunStarted",
]
