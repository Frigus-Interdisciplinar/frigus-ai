"""Qual provider atende cada modelo e qual classe LangChain o constrói."""

from collections.abc import Callable, Mapping
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from frigus_ai.settings.llm import Model

type Provider = Literal[
    "gemini", 
    "groq", 
    "claude", 
    "openrouter", 
    "gateway"
]

PROVIDER_MAP: Mapping[Model, Provider] = {
    Model.GEMINI_FLASH:        "gemini",
    Model.GPT_OSS_120B:        "groq",
    Model.CLAUDE_HAIKU:        "claude",
    Model.CLAUDE_SONNET:       "claude",
    Model.QWEN_3_8_FREE:       "openrouter",
    Model.GPT_6_LUNA:          "gateway",
}

BUILDERS: Mapping[Provider, Callable[..., BaseChatModel]] = {
    "gemini":     ChatGoogleGenerativeAI,
    "groq":       ChatGroq,
    "claude":     ChatAnthropic,
    "openrouter": ChatOpenAI,
    "gateway":    ChatOpenAI,
}

__all__ = ["BUILDERS", "PROVIDER_MAP", "Provider"]
