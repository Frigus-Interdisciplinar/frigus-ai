"""
Auth por API key: o que se testa aqui é a dependência (bypass, 401, resolução do
user_id) e a rota de emissão — sem Redis/Postgres, ambos trocados por stubs.
"""

import pytest
from fastapi.testclient import TestClient

from interfaces.api import auth
from interfaces.api.main import app
from interfaces.api.routes import chats as rotas
from interfaces.api.routes import keys as rotas_keys

CHAT_ID = "chat-de-teste"


@pytest.fixture
def cliente(monkeypatch):
    async def _iniciar_sessao(user_id):
        return 1

    async def _get_history(session_id, user_id, limit=5):
        _get_history.chamado_com = (session_id, user_id)
        return []

    monkeypatch.setattr(rotas.chat_service, "iniciar_sessao", _iniciar_sessao)
    monkeypatch.setattr(rotas.chat_service, "get_history", _get_history)
    return TestClient(app), _get_history


def test_auth_desligada_usa_usuario_demo(cliente, monkeypatch):
    client, get_history = cliente
    monkeypatch.setattr(auth.settings, "API_KEY_AUTH_ENABLED", False)

    assert client.get(f"/chats/{CHAT_ID}/messages").status_code == 200
    assert get_history.chamado_com == (CHAT_ID, auth.chat_service.DEMO_USER_ID)


def test_auth_ligada_sem_key_vira_401(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings, "API_KEY_AUTH_ENABLED", True)

    assert client.get(f"/chats/{CHAT_ID}/messages").status_code == 401


def test_auth_ligada_resolve_user_id_da_key(cliente, monkeypatch):
    client, get_history = cliente
    monkeypatch.setattr(auth.settings, "API_KEY_AUTH_ENABLED", True)
    monkeypatch.setattr(auth, "get_user_id_by_api_key", lambda key: 42 if key == "boa" else None)

    r = client.get(f"/chats/{CHAT_ID}/messages", headers={"X-API-Key": "boa"})

    assert r.status_code == 200
    assert get_history.chamado_com == (CHAT_ID, 42)

    assert client.get(f"/chats/{CHAT_ID}/messages", headers={"X-API-Key": "ruim"}).status_code == 401


def test_signup_secret_vazio_nao_libera_emissao_de_key(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings, "SIGNUP_SECRET", "")

    r = client.post("/keys", json={"nome": "Ana", "email": "ana@frigus.com"})

    assert r.status_code == 401


def test_emissao_de_key_devolve_key_em_claro_uma_vez(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings, "SIGNUP_SECRET", "segredo")

    async def _criar_usuario(nome, email):
        return 7

    monkeypatch.setattr(rotas_keys.chat_service, "criar_usuario", _criar_usuario)
    monkeypatch.setattr(rotas_keys, "allocate_api_key", lambda user_id, api_key: True)

    r = client.post(
        "/keys",
        json={"nome": "Ana", "email": "ana@frigus.com"},
        headers={"X-Signup-Secret": "segredo"},
    )

    assert r.status_code == 201
    assert r.json()["user_id"] == 7
    assert len(r.json()["api_key"]) > 20


def test_key_duplicada_vira_409(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings, "SIGNUP_SECRET", "segredo")

    async def _criar_usuario(nome, email):
        return 7

    monkeypatch.setattr(rotas_keys.chat_service, "criar_usuario", _criar_usuario)
    monkeypatch.setattr(rotas_keys, "allocate_api_key", lambda user_id, api_key: False)

    r = client.post(
        "/keys",
        json={"nome": "Ana", "email": "ana@frigus.com"},
        headers={"X-Signup-Secret": "segredo"},
    )

    assert r.status_code == 409


def test_email_invalido_vira_422(cliente, monkeypatch):
    client, _ = cliente
    monkeypatch.setattr(auth.settings, "SIGNUP_SECRET", "segredo")

    r = client.post(
        "/keys",
        json={"nome": "Ana", "email": "sem-arroba"},
        headers={"X-Signup-Secret": "segredo"},
    )

    assert r.status_code == 422
