from enum import StrEnum

from pydantic import BaseModel, SecretStr


class Model(StrEnum):
    """Catálogo de modelos — dado puro, sem dependência de LangChain."""

    GEMINI_FLASH        = "gemini-3.6-flash"
    GPT_OSS_120B        = "openai/gpt-oss-120b"
    CLAUDE_HAIKU        = "claude-haiku-4-5"
    CLAUDE_SONNET       = "claude-sonnet-4-6"
    QWEN_3_8_FREE       = "qwen/qwen3.8-27b:free"
    EMBEDDING_MODEL     = "gemini-embedding-001"


class LLMSettings(BaseModel):
    gemini_api_key: SecretStr
    groq_api_key: SecretStr
    anthropic_api_key: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")

    embedding_model: Model = Model.EMBEDDING_MODEL

    default_temperature: float = 0.7
    guardrail_temperature: float = 0.0  # guardrails, juiz e roteador: saída determinística
    vision_temperature: float = 0.1

    # Limites do grafo. max_historico_mensagens ≈ 3 mensagens por turno (21 ≈ 7 turnos).
    max_historico_mensagens: int = 21
    max_tentativas_juiz: int = 2

    @property
    def provider_keys(self) -> dict[str, SecretStr]:
        return {
            "gemini": self.gemini_api_key,
            "groq": self.groq_api_key,
            "claude": self.anthropic_api_key,
            "openrouter": self.openrouter_api_key,
        }
