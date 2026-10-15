from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq
from pydantic import BaseModel

from frigus_ai.graph.state import InventarioGeladeira
from frigus_ai.infra.llm import build_llm
from frigus_ai.settings import settings
from frigus_ai.settings.llm import Model

_cfg = settings.llm


def _cadeia(modelos: tuple[BaseChatModel | None, ...]) -> list[BaseChatModel]:
    return [m for m in modelos if m is not None]  # None = provider sem API key


def com_reserva(primario: BaseChatModel | None, *reservas: BaseChatModel | None):
    """O primeiro modelo disponível, com os demais de fallback. `None` se nenhum tiver chave."""

    cadeia = _cadeia((primario, *reservas))
    if not cadeia:
        return None
    return cadeia[0].with_fallbacks(cadeia[1:]) if cadeia[1:] else cadeia[0]


def estruturado(schema: type[BaseModel], primario: BaseChatModel | None, *reservas: BaseChatModel | None):
    """
    `with_structured_output` em cada modelo da cadeia, com fallback entre eles. `RunnableWithFallbacks`
    não tem `with_structured_output`, então a saída estruturada vem antes da cadeia. Groq usa
    `json_schema`: com o `function_calling` padrão o gpt-oss responde 400 ("Tool choice is required").
    """

    cadeia = _cadeia((primario, *reservas))
    if not cadeia:
        return None
    runs = [
        m.with_structured_output(schema, **({"method": "json_schema"} if isinstance(m, ChatGroq) else {}))
        for m in cadeia
    ]
    return runs[0].with_fallbacks(runs[1:]) if runs[1:] else runs[0]


_llm_visao_base  = build_llm(Model.GEMINI_FLASH, _cfg.vision_temperature, _cfg, timeout_s=_cfg.timeout_visao_s)
llm_gemini       = build_llm(Model.GEMINI_FLASH, _cfg.default_temperature, _cfg, top_p=0.95)
llm_groq         = build_llm(Model.GPT_OSS_120B, _cfg.default_temperature, _cfg)
llm_rapido       = build_llm(Model.GPT_OSS_120B, _cfg.guardrail_temperature, _cfg, timeout_s=_cfg.timeout_curto_s)
llm_guardrail    = build_llm(Model.GEMINI_FLASH, _cfg.guardrail_temperature, _cfg, timeout_s=_cfg.timeout_curto_s)
llm_juiz         = build_llm(Model.GEMINI_FLASH, _cfg.guardrail_temperature, _cfg, timeout_s=_cfg.timeout_curto_s)
llm_openrouter   = build_llm(Model.QWEN_3_8_FREE, _cfg.default_temperature, _cfg)
llm_luna         = build_llm(Model.GPT_5_6_LUNA, _cfg.default_temperature, _cfg)

llm_visao        = estruturado(InventarioGeladeira, _llm_visao_base, llm_luna)  
llm_especialista = com_reserva(llm_gemini, llm_groq, llm_luna, llm_openrouter)
llm_agil         = com_reserva(llm_rapido, llm_guardrail, llm_luna)  


__all__ = [
    "com_reserva",
    "estruturado",
    "llm_agil",
    "llm_especialista",
    "llm_gemini",
    "llm_groq",
    "llm_guardrail",
    "llm_juiz",
    "llm_luna",
    "llm_openrouter",
    "llm_rapido",
    "llm_visao",
]
