"""Callback do LangChain que alimenta as métricas de tool/LLM — uma instância por turno."""

import time
from dataclasses import dataclass
from typing import Any, get_args
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import LLMResult

from frigus_ai.evals.metrics import (
    LLM_DURATION,
    LLM_RUNS,
    LLM_TOKENS,
    TOOL_DURATION,
    TOOL_RUNS,
)
from frigus_ai.graph.names import NodeLiteral
from frigus_ai.models import Model

_ALLOWED_NODES = frozenset(get_args(NodeLiteral))
_ALLOWED_PROVIDERS = frozenset({"google_genai", "groq", "anthropic", "openai"})
_ALLOWED_MODELS = frozenset(m.value for m in Model)


@dataclass(frozen=True, slots=True)
class _ToolRun:
    name: str
    started_at: float


@dataclass(frozen=True, slots=True)
class _LLMRun:
    provider: str
    model: str
    node: str
    started_at: float


def _bounded_label(value: object, allowed: frozenset[str]) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return "unknown"


def _tool_name(serialized: dict[str, Any]) -> str:
    name = serialized.get("name")

    if not isinstance(name, str):
        return "unknown"

    # Nomes de tool vêm do próprio código (StructuredTool), nunca de input do usuário.
    return name[:100]


def _usage_tokens(response: LLMResult) -> tuple[int, int]:
    input_tokens = 0
    output_tokens = 0

    for generation_list in response.generations:
        for generation in generation_list:
            message = getattr(generation, "message", None)

            if not isinstance(message, AIMessage) or message.usage_metadata is None:
                continue

            usage = message.usage_metadata
            input_tokens += usage.get("input_tokens", 0)
            output_tokens += usage.get("output_tokens", 0)

    return input_tokens, output_tokens


class PrometheusCallbackHandler(BaseCallbackHandler):
    """
    Uma instância por chamada a `runner.executar()` — os mapas de `run_id` não ficam
    compartilhados entre turnos/usuários concorrentes. Guarda só nomes e timestamps, nunca
    prompts, argumentos de tool ou conteúdo de resposta.
    """

    def __init__(self) -> None:
        self._tools: dict[UUID, _ToolRun] = {}
        self._llms: dict[UUID, _LLMRun] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        del input_str, parent_run_id, kwargs
        self._tools[run_id] = _ToolRun(name=_tool_name(serialized), started_at=time.perf_counter())

    def on_tool_end(
        self, output: Any, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        del output, parent_run_id, kwargs
        self._finish_tool(run_id, termination="returned")

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        del error, parent_run_id, kwargs
        self._finish_tool(run_id, termination="raised")

    def _finish_tool(self, run_id: UUID, termination: str) -> None:
        tool = self._tools.pop(run_id, None)

        if tool is None:
            return

        duration = time.perf_counter() - tool.started_at
        TOOL_RUNS.labels(tool=tool.name, termination=termination).inc()
        TOOL_DURATION.labels(tool=tool.name, termination=termination).observe(duration)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, messages, parent_run_id, tags, kwargs
        run_metadata = metadata or {}

        self._llms[run_id] = _LLMRun(
            provider=_bounded_label(run_metadata.get("ls_provider"), _ALLOWED_PROVIDERS),
            model=_bounded_label(run_metadata.get("ls_model_name"), _ALLOWED_MODELS),
            node=_bounded_label(run_metadata.get("langgraph_node"), _ALLOWED_NODES),
            started_at=time.perf_counter(),
        )

    def on_llm_end(
        self, response: LLMResult, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        del parent_run_id, kwargs
        run = self._llms.pop(run_id, None)

        if run is None:
            return

        input_tokens, output_tokens = _usage_tokens(response)
        duration = time.perf_counter() - run.started_at
        labels = {"provider": run.provider, "model": run.model, "node": run.node}

        LLM_RUNS.labels(**labels, outcome="success").inc()
        LLM_DURATION.labels(**labels, outcome="success").observe(duration)
        LLM_TOKENS.labels(provider=run.provider, model=run.model, direction="input").inc(input_tokens)
        LLM_TOKENS.labels(provider=run.provider, model=run.model, direction="output").inc(output_tokens)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        del error, parent_run_id, kwargs
        run = self._llms.pop(run_id, None)

        if run is None:
            return

        duration = time.perf_counter() - run.started_at
        labels = {"provider": run.provider, "model": run.model, "node": run.node}
        LLM_RUNS.labels(**labels, outcome="error").inc()
        LLM_DURATION.labels(**labels, outcome="error").observe(duration)


__all__ = ["PrometheusCallbackHandler"]
