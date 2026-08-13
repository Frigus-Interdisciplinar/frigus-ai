from typing import Optional
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from config.models import Model, PROVIDER_MAP, BUILDERS, API_KEYS


def build_llm(
    temperature: float,
    top_p: Optional[float] = None,
    model: Optional[str] = None
) -> ChatGoogleGenerativeAI | ChatGroq | ChatAnthropic:
    """
    Cria uma LLM com base no modelo informado.
    top_p só é aplicado para modelos Gemini.
    """

    provider = PROVIDER_MAP.get(model)

    if provider is None:
        raise ValueError(f"Modelo desconhecido: {model}")

    kwargs = dict(
        model=model,
        temperature=temperature,
        api_key=API_KEYS.get(provider),
    )

    # se fizer somente if top_p e valor dele seja 0.0, o python interpreta como False (mto legal)
    if top_p is not None and provider == "gemini":
        kwargs["top_p"] = top_p

    return BUILDERS[provider](**kwargs)


llm_gemini       = build_llm(model=Model.GEMINI_2_5_FLASH, temperature=0.7, top_p=0.95)
llm_groq         = build_llm(model=Model.LLAMA_3_3_VERSATILE, temperature=0.7)
llm_rapido       = build_llm(model=Model.LLAMA_3_3_VERSATILE, temperature=0.0)
llm_guardrail    = build_llm(model=Model.GEMINI_2_5_FLASH, temperature=0.0)
llm_juiz         = build_llm(model=Model.GEMINI_2_5_FLASH, temperature=0.0)
llm_especialista = llm_gemini.with_fallbacks([llm_groq])


__all__ = [
    "llm_gemini",
    "llm_groq",
    "llm_rapido",
    "llm_especialista",
    "llm_guardrail",
    "llm_juiz",
]
