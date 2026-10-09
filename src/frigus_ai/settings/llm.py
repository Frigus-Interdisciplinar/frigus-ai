from enum import StrEnum

from pydantic import BaseModel, SecretStr


class Model(StrEnum):
    """Catálogo de modelos — dado puro, sem dependência de LangChain."""

    GEMINI_FLASH        = "gemini-3.6-flash"
    GPT_OSS_120B        = "openai/gpt-oss-120b"
    CLAUDE_HAIKU        = "claude-haiku-4-5"
    CLAUDE_SONNET       = "claude-sonnet-4-6"
    GPT_5_6_LUNA        = "gpt-5.6-luna"
    QWEN_3_8_FREE       = "qwen/qwen3.8-27b:free"
    EMBEDDING_MODEL     = "gemini-embedding-001"


class ProviderPolicy(BaseModel):
    """
    Quanto esperar por um provider antes do `with_fallbacks` assumir. `timeout_s` é por tentativa;
    `retries` são tentativas extras (pior caso: `(retries + 1) * timeout_s`).
    """

    timeout_s: float = 30.0
    retries: int = 0


class LLMSettings(BaseModel):
    gemini_api_key: SecretStr
    groq_api_key: SecretStr
    anthropic_api_key: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")

    embedding_model: Model = Model.EMBEDDING_MODEL

    # Provider caído (503, cota) não pode segurar o turno. Env: LLM__GEMINI_TIMEOUT_S=15. Campos
    # planos: sobrescrever uma chave de dict por env substitui o dict inteiro.
    gemini_timeout_s: float = 30.0
    gemini_retries: int = 0
    groq_timeout_s: float = 30.0
    groq_retries: int = 1  # 429 por rajada costuma passar em segundos
    claude_timeout_s: float = 60.0
    claude_retries: int = 1
    openrouter_timeout_s: float = 30.0
    openrouter_retries: int = 0
    openai_timeout_s: float = 45.0  # modelo de raciocínio, mais lento que os outros
    openai_retries: int = 1
    # Teto menor pra quem devolve saída curta e estruturada (guardrail, juiz, roteador, fatos/resumo).
    timeout_curto_s: float = 15.0
    # Foto + inventário estruturado é a chamada mais pesada.
    timeout_visao_s: float = 60.0

    default_temperature: float = 0.7
    guardrail_temperature: float = 0.0  # guardrails, juiz e roteador: saída determinística
    vision_temperature: float = 0.1

    # Limites do grafo. max_historico_mensagens ≈ 3 mensagens por turno (21 ≈ 7 turnos).
    max_historico_mensagens: int = 21
    max_tentativas_juiz: int = 2

    def policy(self, provider: str) -> ProviderPolicy:
        return ProviderPolicy(
            timeout_s=getattr(self, f"{provider}_timeout_s"),
            retries=getattr(self, f"{provider}_retries"),
        )

    @property
    def provider_keys(self) -> dict[str, SecretStr]:
        return {
            "gemini": self.gemini_api_key,
            "groq": self.groq_api_key,
            "claude": self.anthropic_api_key,
            "openrouter": self.openrouter_api_key,
            "openai": self.openai_api_key,
        }
