import os

from pydantic import SecretStr
from pydantic_settings import BaseSettings


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

    API_KEY_AUTH_ENABLED: bool
    SIGNUP_SECRET: str = ""

    A2A_BASE_URL: str

    QDRANT_URL: str
    QDRANT_API_KEY: SecretStr = SecretStr("")
    QDRANT_COLLECTION_NAME: str

    PROMETHEUS_URL: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()  # type: ignore[call-arg,misc]

if settings.LANGSMITH_TRACING:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY.get_secret_value()
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
