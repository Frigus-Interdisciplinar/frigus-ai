"""Qual provider atende cada modelo e qual classe LangChain o constrói."""

from collections.abc import Callable, Mapping
from functools import partial
from typing import Final, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from frigus_ai.settings.llm import Model

type Provider = Literal["gemini", "groq", "claude", "openrouter"]

PROVIDER_MAP: Final[Mapping[Model, Provider]] = {
    Model.GEMINI_FLASH:        "gemini",
    Model.GPT_OSS_120B:        "groq",
    Model.CLAUDE_HAIKU:        "claude",
    Model.CLAUDE_SONNET:       "claude",
    Model.QWEN_3_8_FREE:       "openrouter",
}

BUILDERS: Final[Mapping[Provider, Callable[..., BaseChatModel]]] = {
    "gemini": ChatGoogleGenerativeAI,
    "groq":   ChatGroq,
    "claude": ChatAnthropic,
    "openrouter": partial(ChatOpenAI, base_url="https://openrouter.ai/api/v1"),
}

__all__ = ["BUILDERS", "PROVIDER_MAP", "Provider"]
