"""Callback do LangChain que alimenta as métricas de tool/LLM — uma instância por turno."""

import time
from dataclasses import dataclass
from typing import Any, NamedTuple, get_args
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import LLMResult

from frigus_ai.graph.names import COMPRAS, ESTOQUE, FINANCEIRO, RECEITAS, NodeLiteral
from frigus_ai.settings.llm import Model
from frigus_ai.telemetry.metrics import (
    LLM_COST,
    LLM_DURATION,
    LLM_FALLBACKS,
    LLM_RUNS,
    LLM_TOKENS,
    TOOL_DURATION,
    TOOL_RUNS,
)

_ALLOWED_NODES = frozenset(get_args(NodeLiteral))
_ALLOWED_PROVIDERS = frozenset({"google_genai", "groq", "anthropic", "openai"})
_ALLOWED_MODELS = frozenset(m.value for m in Model)

# Nodes que usam `llm_especialista` (Luna com fallback — graph/llm.py): outro modelo
# respondendo neles é fallback.
_NODES_ESPECIALISTA = frozenset({ESTOQUE, COMPRAS, RECEITAS, FINANCEIRO})
_MODELO_ESPECIALISTA = Model.GPT_6_LUNA.value


class PrecoPor1MTokens(NamedTuple):
    entrada: float
    saida: float


# USD por 1M de tokens, preço cheio. Modelo fora da tabela custa 0 (subestima, não inventa).
# Conferido em 2026-10-11 (ai.google.dev/gemini-api/docs/pricing, console.groq.com/docs/models e
# vercel.com/ai-gateway/models).
# ponytail: o Gemini 3.6 Flash dobra pra 1.50/7.50 em 2027-01-01 — atualizar nessa data.
PRECOS_POR_1M_TOKENS: dict[str, PrecoPor1MTokens] = {
    Model.GEMINI_FLASH: PrecoPor1MTokens(entrada=0.75, saida=3.75),
    Model.GPT_OSS_120B: PrecoPor1MTokens(entrada=0.15, saida=0.60),
    Model.QWEN_3_8_FREE: PrecoPor1MTokens(entrada=0.0, saida=0.0),
    Model.GPT_6_LUNA: PrecoPor1MTokens(entrada=0.10, saida=0.50),
    Model.JEV: PrecoPor1MTokens(entrada=0.04, saida=0.0),
}


def custo_usd(modelo: str, tokens_entrada: float, tokens_saida: float) -> float:
    preco = PRECOS_POR_1M_TOKENS.get(modelo, PrecoPor1MTokens(0.0, 0.0))
    return (tokens_entrada * preco.entrada + tokens_saida * preco.saida) / 1_000_000


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


def no_do_grafo(metadata: dict[str, Any]) -> str:
    """O node do NOSSO grafo. Dentro de um especialista (`create_agent`), `langgraph_node` é o
    node interno do agente ("model", "tools") — o nosso vem no começo do `checkpoint_ns`."""

    candidatos = [
        parte.split(":", 1)[0]
        for parte in str(metadata.get("langgraph_checkpoint_ns") or "").split("|")
        if parte
    ]
    candidatos.append(str(metadata.get("langgraph_node") or ""))

    return next((c for c in candidatos if c in _ALLOWED_NODES), "unknown")


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
    """Uma instância por turno (os mapas de `run_id` não vazam entre usuários). Guarda só nomes e
    timestamps, nunca prompts nem conteúdo."""

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
            node=no_do_grafo(run_metadata),
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
        LLM_COST.labels(provider=run.provider, model=run.model).inc(
            custo_usd(run.model, input_tokens, output_tokens)
        )
        if run.node in _NODES_ESPECIALISTA and run.model != _MODELO_ESPECIALISTA:
            LLM_FALLBACKS.labels(node=run.node, model=run.model).inc()

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


__all__ = ["PRECOS_POR_1M_TOKENS", "PrecoPor1MTokens", "PrometheusCallbackHandler", "custo_usd", "no_do_grafo"]
