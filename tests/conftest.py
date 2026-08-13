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
os.environ.setdefault("DATABASE_URI", "postgresql://test:test@localhost:5432/test")
