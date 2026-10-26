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
    timeout_s: float = 15.0
    retries:   int = 0


class GeminiSettings(Provedor):
    """Só os embeddings (FAQ e conversas anteriores); os modelos de chat passam pelo gateway."""

    api_key: SecretStr


class GroqSettings(Provedor):
    """
    Reserva. Sem retry: o 429 do plano gratuito é por tokens/minuto (`retry-after` ~20s), então
    esperar só atrasa o turno; melhor cair logo no próximo elo da cadeia.
    """

    api_key: SecretStr


class ClaudeSettings(Provedor):
    """Opcional, fora das cadeias por padrão."""

    timeout_s: float = 60.0
    retries:   int = 1


class GatewaySettings(Provedor):
    """Vercel AI Gateway, pago: GPT-6 Luna em todas as cadeias de chat e JeV no guardrail, roteador e juiz."""

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
    timeout_curto_s: float = 8.0
    timeout_visao_s: float = 30.0

    # Guardrails, juiz e roteador usam a temperatura 0: saída determinística.
    default_temperature:   float = 0.7
    guardrail_temperature: float = 0.0
    vision_temperature:    float = 0.1

    # Limites do grafo. ~3 mensagens por turno: 21 ≈ 7 turnos de histórico.
    max_historico_mensagens: int = 21
    max_reescritas_juiz:     int = 2

    # Item da foto com chance de aparecer abaixo disso vai pro usuário confirmar. Chute: não foi
    # calibrado com fotos reais (ver "Confiança não é probabilidade de acerto" em .agents/skills/jev.md).
    confianca_minima_item_visao: float = 0.7

    # Nome que o usuário disse -> item do estoque: abaixo disso a tool pergunta qual em vez de escolher.
    # Chute, sem calibração.
    confianca_minima_nome: float = 0.7

    # Resposta que o Juiz acha "sustentada" com chance menor que isso é tratada como sem evidência.
    # Calibrado em 2026-10-23 com 24 respostas reais: as com fato inventado ficaram em 0,00 a 0,28 e as
    # corretas em 0,49 a 0,98; 0,4 fica no vão. Com 0,8 o juiz reprovava respostas corretas (0,7 a 0,77)
    # e forçava até duas reescritas por turno. Amostra pequena: reavaliar com mais casos.
    confianca_minima_grounding: float = 0.4
