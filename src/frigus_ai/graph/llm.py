from frigus_ai.graph.state import InventarioGeladeira
from frigus_ai.infra.llm import build_llm
from frigus_ai.settings import settings
from frigus_ai.settings.llm import Model

_cfg = settings.llm

_llm_visao_base  = build_llm(Model.GEMINI_FLASH, _cfg.vision_temperature, _cfg)
llm_visao        = _llm_visao_base.with_structured_output(InventarioGeladeira) if _llm_visao_base else None
llm_gemini       = build_llm(Model.GEMINI_FLASH, _cfg.default_temperature, _cfg, top_p=0.95)
llm_groq         = build_llm(Model.GPT_OSS_120B, _cfg.default_temperature, _cfg)
llm_rapido       = build_llm(Model.GPT_OSS_120B, _cfg.guardrail_temperature, _cfg)
llm_guardrail    = build_llm(Model.GEMINI_FLASH, _cfg.guardrail_temperature, _cfg)
llm_juiz         = build_llm(Model.GEMINI_FLASH, _cfg.guardrail_temperature, _cfg)
llm_openrouter   = build_llm(Model.QWEN_3_8_FREE, _cfg.default_temperature, _cfg)
llm_especialista = llm_gemini.with_fallbacks([m for m in (llm_groq, llm_openrouter) if m])


__all__ = [
    "llm_especialista",
    "llm_gemini",
    "llm_groq",
    "llm_guardrail",
    "llm_juiz",
    "llm_openrouter",
    "llm_rapido",
    "llm_visao",
]
