"""
Primeiro teste de API do repo. Não sobe Postgres/Mongo/Redis: `chat_service` é
trocado por stubs, então o que se testa é o contrato HTTP das rotas (status,
headers, body) — não o domínio, que já tem teste próprio.
"""

import pytest
from fastapi.testclient import TestClient

from frigus_ai.chat.service import LimiteDeMensagensExcedido
from interfaces.api.main import app
from interfaces.api.routes import chats as rotas

CHAT_ID = "chat-de-teste"


@pytest.fixture
def cliente(monkeypatch):
    async def _iniciar_sessao(user_id):
        return 1

    monkeypatch.setattr(rotas.chat_service, "iniciar_sessao", _iniciar_sessao)
    return TestClient(app)


def _stub_send_message(monkeypatch, erro: Exception):
    async def _falha(*args, **kwargs):
        raise erro

    monkeypatch.setattr(rotas.chat_service, "send_message", _falha)


def test_limite_de_mensagens_vira_429_com_retry_after(cliente, monkeypatch):
    _stub_send_message(monkeypatch, LimiteDeMensagensExcedido("Você atingiu o limite."))

    r = cliente.post(f"/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
    assert "limite" in r.json()["detail"].lower()


def test_erro_generico_vira_500_sem_vazar_mensagem_interna(cliente, monkeypatch):
    interno = "FATAL: password authentication failed for user postgres"
    _stub_send_message(monkeypatch, RuntimeError(interno))

    r = cliente.post(f"/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 500
    assert interno not in r.text
    assert r.json()["detail"] == "Erro interno ao processar a mensagem."


def test_send_message_ok(cliente, monkeypatch):
    async def _ok(conteudo, chat_id, user_id, stock_id):
        return f"eco: {conteudo}"

    monkeypatch.setattr(rotas.chat_service, "send_message", _ok)

    r = cliente.post(f"/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 200
    assert r.json() == {"chat_id": CHAT_ID, "content": "eco: oi"}


def test_delete_chat_devolve_202_e_agenda_encerramento(cliente, monkeypatch):
    chamadas = []

    async def _encerrar(session_id, user_id):
        chamadas.append((session_id, user_id))

    monkeypatch.setattr(rotas.chat_service, "encerrar_sessao", _encerrar)

    r = cliente.delete(f"/chats/{CHAT_ID}")

    assert r.status_code == 202
    # TestClient roda as background tasks antes de devolver a resposta
    assert chamadas == [(CHAT_ID, rotas.chat_service.DEMO_USER_ID)]
