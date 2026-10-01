import pytest
from pydantic import ValidationError

from frigus_ai.settings import Settings

_BASE = {
    "database": {"qdrant_collection_name": "faq-test"},
    "observability": {"langsmith_tracing": False, "langsmith_api_key": "", "langsmith_project": "t"},
}


def _settings(*, environment="local", key_auth_enabled=False, cors_origins=("*",)) -> Settings:
    return Settings(
        environment=environment,
        api={"key_auth_enabled": key_auth_enabled, "cors_origins": list(cors_origins), "a2a_base_url": "http://x"},
        **_BASE,
    )


def test_producao_sem_auth_aborta():
    with pytest.raises(ValidationError, match="KEY_AUTH_ENABLED"):
        _settings(environment="production", cors_origins=("https://app.frigus.com",))


def test_producao_com_cors_aberto_aborta():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _settings(environment="production", key_auth_enabled=True)


def test_producao_com_auth_e_cors_fechado_ok():
    s = _settings(environment="production", key_auth_enabled=True, cors_origins=("https://app.frigus.com",))
    assert s.environment == "production"


def test_local_sem_auth_ok():
    assert _settings().api.key_auth_enabled is False


def test_env_aninhado_com_duplo_underscore(monkeypatch):
    monkeypatch.setenv("LLM__MAX_TENTATIVAS_JUIZ", "5")
    assert _settings().llm.max_tentativas_juiz == 5
