import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GROQ_API_KEY: str
    ANTHROPIC_API_KEY: str = ""

    POSTGRES_URI: str
    MONGODB_URI: str = "mongodb://localhost:27017"

    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "frigus-ai"

    SPOONACULAR_API_KEY: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_NAME: str = "faq"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()

# O SDK do LangSmith lê os.environ direto (dentro do langchain-core) — o objeto
# Settings acima não é o suficiente pra ativar o tracing.
if settings.LANGSMITH_TRACING:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
