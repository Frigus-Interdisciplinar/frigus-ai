from langchain_core.language_models import BaseChatModel

from frigus_ai.infra.llm.registry import BUILDERS, PROVIDER_MAP
from frigus_ai.settings.llm import LLMSettings, Model


def build_llm(
    model: Model,
    temperature: float,
    llm_settings: LLMSettings,
    top_p: float | None = None,
    timeout_s: float | None = None,
) -> BaseChatModel | None:
    """
    Cria uma LLM com base no modelo informado.
    top_p só é aplicado para modelos Gemini.
    `timeout_s` sobrepõe o timeout da política do provider (`LLMSettings.policy`) — usado
    pelos papéis de saída curta, que não devem esperar tanto quanto um especialista.
    Devolve None se o provider não tiver API key configurada (providers opcionais).
    """

    provider = PROVIDER_MAP.get(model)
    if provider is None:
        raise ValueError(f"Modelo desconhecido: {model}")

    api_key = llm_settings.provider_keys[provider]
    if not api_key:
        return None

    politica = llm_settings.policy(provider)

    kwargs = {
        "model": model.value,
        "temperature": temperature,
        "api_key": api_key.get_secret_value(),
        "timeout": timeout_s if timeout_s is not None else politica.timeout_s,
        # No Gemini `max_retries` conta tentativas TOTAIS (1 = sem retry); nos SDKs da
        # Groq/OpenAI/Anthropic conta as EXTRAS. A política usa sempre "extras".
        "max_retries": politica.retries + 1 if provider == "gemini" else politica.retries,
    }

    if top_p is not None and provider == "gemini":
        kwargs["top_p"] = top_p

    # gpt-oss é modelo de raciocínio: sem isso o chain-of-thought vem dentro do content.
    if provider == "groq":
        kwargs["reasoning_format"] = "hidden"

    return BUILDERS[provider](**kwargs)


__all__ = ["build_llm"]
