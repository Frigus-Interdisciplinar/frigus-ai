from enum import StrEnum

from pydantic import BaseModel, SecretStr


class Model(StrEnum):
    """Catálogo de modelos — dado puro, sem dependência de LangChain."""

    GEMINI_FLASH         = "gemini-3.6-flash"
    GPT_OSS_120B         = "openai/gpt-oss-120b"
    CLAUDE_HAIKU         = "claude-haiku-4-5"
    CLAUDE_SONNET        = "claude-sonnet-4-6"
    GPT_6_LUNA           = "openai/gpt-6-luna"
    GPT_6_LUNA_DECISIONS = "openai/gpt-6-luna-decisions"
    JEV                  = "typesafe-ai/jev"
    QWEN_3_8_FREE        = "qwen/qwen3.8-27b:free"
    EMBEDDING_MODEL      = "gemini-embedding-001"


class Provedor(BaseModel):
    """Chave, URL e paciência de um provider. `retries` são tentativas extras: pior caso
    `(retries + 1) * timeout_s` antes do `with_fallbacks` assumir."""

    api_key:   SecretStr = SecretStr("")
    base_url:  str | None = None
    timeout_s: float = 30.0
    retries:   int = 0


class GeminiSettings(Provedor):
    """Principal dos especialistas, guardrail, juiz e visão; também gera os embeddings."""

    api_key: SecretStr


class GroqSettings(Provedor):
    """Primeira reserva. 429 por rajada costuma passar em segundos, daí 1 retry."""

    api_key: SecretStr
    retries: int = 1


class ClaudeSettings(Provedor):
    """Opcional, fora das cadeias por padrão."""

    timeout_s: float = 60.0
    retries:   int = 1


class GatewaySettings(Provedor):
    """Vercel AI Gateway: GPT-6 Luna nas cadeias e JeV no guardrail. Luna raciocina, é mais lento."""

    base_url:  str = "https://ai-gateway.vercel.sh/v1"
    timeout_s: float = 45.0
    retries:   int = 1


class OpenRouterSettings(Provedor):
    """Último elo das cadeias."""

    base_url: str = "https://openrouter.ai/api/v1"


class LLMSettings(BaseModel):
    gemini:     GeminiSettings
    groq:       GroqSettings
    claude:     ClaudeSettings = ClaudeSettings()
    gateway:    GatewaySettings = GatewaySettings()
    openrouter: OpenRouterSettings = OpenRouterSettings()

    embedding_model: Model = Model.EMBEDDING_MODEL

    # Teto por papel, acima da política do provider: saída curta e estruturada (guardrail, juiz,
    # roteador, fatos, resumo) não espera tanto quanto um especialista; foto é a chamada mais pesada.
    timeout_curto_s: float = 15.0
    timeout_visao_s: float = 60.0

    # Guardrails, juiz e roteador usam a temperatura 0: saída determinística.
    default_temperature:   float = 0.7
    guardrail_temperature: float = 0.0
    vision_temperature:    float = 0.1

    # Limites do grafo. ~3 mensagens por turno: 21 ≈ 7 turnos de histórico.
    max_historico_mensagens: int = 21
    max_reescritas_juiz:     int = 2
