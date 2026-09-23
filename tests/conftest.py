"""
Env vars dummy antes de qualquer import de `frigus_ai`.

`frigus_ai/tools/__init__.py` importa os cores das tools, que puxam a cadeia até
`config/settings.py:Settings()` — validado no import do módulo. Ou seja, até um
teste de função pura (`tools/response.py`) quebra na coleção sem as vars
obrigatórias. Como nenhum teste faz I/O real, valores fake resolvem, e a suíte
roda sem `.env` (local ou CI).

`setdefault` para não sobrescrever um `.env` real de quem roda localmente.
"""

import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")

# Vazio, não "test-key": código de produção trata provider/feature sem key como
# opcional (`if not settings.X_API_KEY`) — um dummy não-vazio mudaria esse caminho
# nos testes (ver test_build_llm_sem_api_key_devolve_none).
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("LANGSMITH_API_KEY", "")
os.environ.setdefault("SPOONACULAR_API_KEY", "")
os.environ.setdefault("QDRANT_API_KEY", "")
os.environ.setdefault("SIGNUP_SECRET", "")

os.environ.setdefault("POSTGRES_URI", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("NEO4J_URI", "bolt://neo4j:test@localhost:7687")

os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGSMITH_PROJECT", "frigus-ai-test")

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

os.environ.setdefault("API_KEY_AUTH_ENABLED", "false")

os.environ.setdefault("A2A_BASE_URL", "http://localhost:8000")

os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_COLLECTION_NAME", "faq-test")
