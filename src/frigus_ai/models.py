from collections.abc import Callable, Mapping
from enum import StrEnum
from functools import partial
from typing import Final, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from .settings import settings

type Provider = Literal["gemini", "groq", "claude", "openrouter"]
class Model(StrEnum):
    GEMINI_FLASH        = "gemini-3.6-flash"
    GPT_OSS_120B        = "openai/gpt-oss-120b"
    CLAUDE_HAIKU        = "claude-haiku-4-5"
    CLAUDE_SONNET       = "claude-sonnet-4-6"
    GLM_5_2_FREE        = "z-ai/glm-5.2:free"
    EMBEDDING_MODEL     = "gemini-embedding-001"


PROVIDER_MAP: Final[Mapping[Model, Provider]] = {
    Model.GEMINI_FLASH:        "gemini",
    Model.GPT_OSS_120B:        "groq",
    Model.CLAUDE_HAIKU:        "claude",
    Model.CLAUDE_SONNET:       "claude",
    Model.GLM_5_2_FREE:        "openrouter",
}

API_KEYS: Final = {
    "gemini": settings.GEMINI_API_KEY,
    "groq":   settings.GROQ_API_KEY,
    "claude": settings.ANTHROPIC_API_KEY,
    "openrouter": settings.OPENROUTER_API_KEY,
}

BUILDERS: Final[Mapping[Provider, Callable[..., BaseChatModel]]] = {
    "gemini": ChatGoogleGenerativeAI,
    "groq":   ChatGroq,
    "claude": ChatAnthropic,
    "openrouter": partial(ChatOpenAI, base_url="https://openrouter.ai/api/v1"),
}
