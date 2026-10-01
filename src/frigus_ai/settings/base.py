"""
Ponto de entrada da configuração: um único `Settings` com os grupos de `settings/*.py`. No .env o
grupo vira prefixo com `__`: `DATABASE__POSTGRES_URI`, `LLM__GROQ_API_KEY`, `API_KEYS__SIGNUP_SECRET`.
"""

import os
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings

from frigus_ai.settings.api import ApiSettings
from frigus_ai.settings.api_keys import ApiKeysSettings
from frigus_ai.settings.database import DatabaseSettings
from frigus_ai.settings.llm import LLMSettings
from frigus_ai.settings.observability import ObservabilitySettings

Environment = Literal["local", "production"]


class Settings(BaseSettings):
    environment: Environment = "local"

    api: ApiSettings
    database: DatabaseSettings
    api_keys: ApiKeysSettings = ApiKeysSettings()
    llm: LLMSettings
    observability: ObservabilitySettings

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _validar_producao(self) -> Self:
        if self.environment == "production":
            if not self.api.key_auth_enabled:
                raise ValueError("API__KEY_AUTH_ENABLED precisa ser true quando ENVIRONMENT=production")
            if "*" in self.api.cors_origins:
                raise ValueError('API__CORS_ORIGINS não pode conter "*" quando ENVIRONMENT=production')
        return self


settings = Settings()  # type: ignore[call-arg,misc]

if settings.observability.langsmith_tracing:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.observability.langsmith_api_key.get_secret_value()
    os.environ["LANGSMITH_PROJECT"] = settings.observability.langsmith_project
