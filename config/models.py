from enum import StrEnum
from functools import partial

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from .settings import settings

# OpenRouter fala o protocolo da OpenAI — só troca a base URL. O catálogo `:free`
# rotaciona (conferir em openrouter.ai/models); GLM 5.2 foi escolhido por suportar
# tool calling, que o agente especialista exige.
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Model(StrEnum):
    GEMINI_2_5_FLASH    = "gemini-2.5-flash"
    LLAMA_3_3_VERSATILE = "llama-3.3-70b-versatile"
    QWEN_2_5_PRO        = "qwen-2.5-pro"
    CLAUDE_HAIKU        = "claude-haiku-4-5"
    CLAUDE_SONNET       = "claude-sonnet-4-6"
    GLM_5_2_FREE        = "z-ai/glm-5.2:free"
    EMBEDDING_MODEL     = "gemini-embedding-001"


PROVIDER_MAP = {
    Model.GEMINI_2_5_FLASH:    "gemini",
    Model.LLAMA_3_3_VERSATILE: "groq",
    Model.QWEN_2_5_PRO:        "groq",
    Model.CLAUDE_HAIKU:        "claude",
    Model.CLAUDE_SONNET:       "claude",
    Model.GLM_5_2_FREE:        "openrouter",
}

API_KEYS = {
    "gemini": settings.GEMINI_API_KEY,
    "groq":   settings.GROQ_API_KEY,
    "claude": settings.ANTHROPIC_API_KEY,
    "openrouter": settings.OPENROUTER_API_KEY,
}

BUILDERS = {
    "gemini": ChatGoogleGenerativeAI,
    "groq":   ChatGroq,
    "claude": ChatAnthropic,
    "openrouter": partial(ChatOpenAI, base_url=_OPENROUTER_BASE_URL),
}
