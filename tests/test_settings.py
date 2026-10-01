import pytest
from pydantic import ValidationError

from frigus_ai.settings import Settings


def test_producao_sem_auth_aborta():
    with pytest.raises(ValidationError, match="API_KEY_AUTH_ENABLED"):
        Settings(ENVIRONMENT="production", API_KEY_AUTH_ENABLED=False)


def test_producao_com_auth_ok():
    assert Settings(ENVIRONMENT="production", API_KEY_AUTH_ENABLED=True).ENVIRONMENT == "production"


def test_local_sem_auth_ok():
    assert Settings(ENVIRONMENT="local", API_KEY_AUTH_ENABLED=False).API_KEY_AUTH_ENABLED is False
