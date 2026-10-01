import os
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    GEMINI_API_KEY: SecretStr
    GROQ_API_KEY: SecretStr
    ANTHROPIC_API_KEY: SecretStr = SecretStr("")
    OPENROUTER_API_KEY: SecretStr = SecretStr("")

    POSTGRES_URI: str
    MONGODB_URI: str
    NEO4J_URI: str

    LANGSMITH_TRACING: bool
    LANGSMITH_API_KEY: SecretStr
    LANGSMITH_PROJECT: str

    SPOONACULAR_API_KEY: SecretStr = SecretStr("")

    REDIS_URL: str

    ENVIRONMENT: Environment = "local"

    API_KEY_AUTH_ENABLED: bool
    SIGNUP_SECRET: str = ""

    A2A_BASE_URL: str

    ASSESSOR_A2A_URL: str = ""
    ASSESSOR_API_KEY: SecretStr = SecretStr("")

    QDRANT_URL: str
    QDRANT_API_KEY: SecretStr = SecretStr("")
    QDRANT_COLLECTION_NAME: str
    QDRANT_CHATS_COLLECTION: str = "chats"

    PROMETHEUS_URL: str = ""
    METRICS_TOKEN: SecretStr = SecretStr("")

    API_RELOAD: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _exigir_auth_em_producao(self) -> Self:
        if self.ENVIRONMENT == "production" and not self.API_KEY_AUTH_ENABLED:
            raise ValueError("API_KEY_AUTH_ENABLED precisa ser true quando ENVIRONMENT=production")
        return self


settings = Settings()  # type: ignore[call-arg,misc]

if settings.LANGSMITH_TRACING:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY.get_secret_value()
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
