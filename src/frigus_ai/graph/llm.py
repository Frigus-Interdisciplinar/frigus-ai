
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from config.models import API_KEYS, BUILDERS, PROVIDER_MAP, Model


def build_llm(
    temperature: float,
    top_p: float | None = None,
    model: str | None = None
) -> ChatGoogleGenerativeAI | ChatGroq | ChatAnthropic | ChatOpenAI | None:
    """
    Cria uma LLM com base no modelo informado.
    top_p só é aplicado para modelos Gemini.
    Devolve None se o provider não tiver API key configurada (providers opcionais).
    """

    provider = PROVIDER_MAP.get(model)
    api_key = API_KEYS.get(provider)

    if provider is None:
        raise ValueError(f"Modelo desconhecido: {model}")

    if not api_key:
        return None

    kwargs = {
        "model": model,
        "temperature": temperature,
        "api_key": api_key,
    }

    if top_p is not None and provider == "gemini":
        kwargs["top_p"] = top_p

    return BUILDERS[provider](**kwargs)


llm_gemini       = build_llm(model=Model.GEMINI_2_5_FLASH, temperature=0.7, top_p=0.95)
llm_groq         = build_llm(model=Model.LLAMA_3_3_VERSATILE, temperature=0.7)
llm_rapido       = build_llm(model=Model.LLAMA_3_3_VERSATILE, temperature=0.0)
llm_guardrail    = build_llm(model=Model.GEMINI_2_5_FLASH, temperature=0.0)
llm_juiz         = build_llm(model=Model.GEMINI_2_5_FLASH, temperature=0.0)
llm_openrouter   = build_llm(model=Model.GLM_5_2_FREE, temperature=0.7)
llm_especialista = llm_gemini.with_fallbacks([m for m in (llm_groq, llm_openrouter) if m])


__all__ = [
    "llm_especialista",
    "llm_gemini",
    "llm_groq",
    "llm_guardrail",
    "llm_juiz",
    "llm_openrouter",
    "llm_rapido",
]
