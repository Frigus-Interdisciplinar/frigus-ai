"""
Auth por API key: o que se testa aqui é a dependência (bypass, 401, resolução do
user_id) e a rota de emissão — sem Redis/Postgres, ambos trocados por stubs.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from frigus_ai.api.app import app
from frigus_ai.api.auth import dependencies as auth
from frigus_ai.services.auth_service import auth_service
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service

CHAT_ID = "chat-de-teste"


@pytest.fixture
def cliente(monkeypatch):
    async def _resolver_stock_id(user_id):
        return 1

    async def _get_history(session_id, user_id, limit=5):
        _get_history.chamado_com = (session_id, user_id)
        return []

    async def _validar_ownership(chat_id, user_id):
        """Monkeypatch: não acessa MongoDB, assume que o usuário é o dono."""
        return

    monkeypatch.setattr(user_service, "resolver_stock_id", _resolver_stock_id)
    monkeypatch.setattr(chat_service, "get_history", _get_history)
    monkeypatch.setattr(chat_service, "validar_ownership", _validar_ownership)
    return TestClient(app), _get_history


def test_auth_desligada_reaproveita_usuario_local(cliente, monkeypatch):
    client, get_history = cliente
    monkeypatch.setattr(auth.settings.api, "key_auth_enabled", False)

    async def _obter_ou_criar_padrao():
        return "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"

    monkeypatch.setattr(auth.user_service, "obter_ou_criar_padrao", _obter_ou_criar_padrao)

    assert client.get(f"/v1/chats/{CHAT_ID}/messages").status_code == 200
    assert get_history.chamado_com == (CHAT_ID, "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")


def test_auth_ligada_sem_key_vira_401(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings.api, "key_auth_enabled", True)

    assert client.get(f"/v1/chats/{CHAT_ID}/messages").status_code == 401


def test_auth_ligada_resolve_user_id_da_key(cliente, monkeypatch):
    client, get_history = cliente
    monkeypatch.setattr(auth.settings.api, "key_auth_enabled", True)
    monkeypatch.setattr(
        auth.auth_service, "get_user_id_by_api_key", lambda key: 42 if key == "boa" else None
    )

    r = client.get(f"/v1/chats/{CHAT_ID}/messages", headers={"X-API-Key": "boa"})

    assert r.status_code == 200
    assert get_history.chamado_com == (CHAT_ID, 42)

    assert client.get(f"/v1/chats/{CHAT_ID}/messages", headers={"X-API-Key": "ruim"}).status_code == 401


def test_signup_secret_vazio_nao_libera_emissao_de_key(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings.api_keys, "signup_secret", SecretStr(""))

    r = client.post("/keys", json={"nome": "Ana", "email": "ana@frigus.com"})

    assert r.status_code == 401


def test_emissao_de_key_devolve_key_em_claro_uma_vez(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings.api_keys, "signup_secret", SecretStr("segredo"))

    async def _criar_usuario(nome, email):
        return "u-7"

    monkeypatch.setattr(user_service, "criar_usuario", _criar_usuario)
    monkeypatch.setattr(auth_service, "allocate_api_key", lambda user_id, api_key: True)

    r = client.post(
        "/keys",
        json={"nome": "Ana", "email": "ana@frigus.com"},
        headers={"X-Signup-Secret": "segredo"},
    )

    assert r.status_code == 201
    assert r.json()["user_id"] == "u-7"
    assert len(r.json()["api_key"]) > 20


def test_key_duplicada_vira_409(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings.api_keys, "signup_secret", SecretStr("segredo"))

    async def _criar_usuario(nome, email):
        return "u-7"

    monkeypatch.setattr(user_service, "criar_usuario", _criar_usuario)
    monkeypatch.setattr(auth_service, "allocate_api_key", lambda user_id, api_key: False)

    r = client.post(
        "/keys",
        json={"nome": "Ana", "email": "ana@frigus.com"},
        headers={"X-Signup-Secret": "segredo"},
    )

    assert r.status_code == 409


def test_email_invalido_vira_422(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings.api_keys, "signup_secret", SecretStr("segredo"))

    r = client.post(
        "/keys",
        json={"nome": "Ana", "email": "sem-arroba"},
        headers={"X-Signup-Secret": "segredo"},
    )

    assert r.status_code == 422


def test_rotate_exige_key_valida_e_devolve_a_nova(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings.api, "key_auth_enabled", True)
    monkeypatch.setattr(auth_service, "get_user_id_by_api_key", lambda key: "u-7" if key == "boa" else None)
    rotacionadas = []
    monkeypatch.setattr(auth_service, "rotate_api_key", lambda user_id, nova: rotacionadas.append((user_id, nova)))

    assert client.post("/keys/rotate").status_code == 401
    r = client.post("/keys/rotate", headers={"X-API-Key": "boa"})

    assert r.status_code == 200
    assert r.json()["user_id"] == "u-7"
    assert rotacionadas == [("u-7", r.json()["api_key"])]


def test_revoke_devolve_204(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings.api, "key_auth_enabled", True)
    monkeypatch.setattr(auth_service, "get_user_id_by_api_key", lambda key: "u-7")
    revogadas = []
    monkeypatch.setattr(auth_service, "revoke_api_key", lambda user_id: revogadas.append(user_id) or True)

    r = client.delete("/keys", headers={"X-API-Key": "boa"})

    assert r.status_code == 204
    assert revogadas == ["u-7"]
