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

    async def _garantir_limite(user_id):
        return None

    monkeypatch.setattr(rotas.chat_service, "iniciar_sessao", _iniciar_sessao)
    monkeypatch.setattr(rotas.chat_service, "garantir_limite", _garantir_limite)
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
    """
    Quem traduz é o handler de `main.py`, não a rota. `raise_server_exceptions=False`
    porque o TestClient re-levanta a exceção do servidor por padrão — com ele ligado o
    teste vê o RuntimeError cru em vez da resposta que o cliente HTTP receberia.
    """

    interno = "FATAL: password authentication failed for user postgres"
    _stub_send_message(monkeypatch, RuntimeError(interno))

    cliente = TestClient(app, raise_server_exceptions=False)
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


def test_stream_devolve_eventos_por_no_e_resposta(cliente, monkeypatch):
    async def _stream(conteudo, chat_id, user_id, stock_id):
        yield "no", "roteador_node"
        yield "no", "estoque_node"
        yield "resposta", f"eco: {conteudo}"

    monkeypatch.setattr(rotas.chat_service, "stream_message", _stream)

    with cliente.stream(
        "POST", f"/chats/{CHAT_ID}/messages/stream", json={"content": "oi"}
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        corpo = "".join(r.iter_text())

    assert corpo.count("event: no") == 2
    assert "event: resposta" in corpo
    assert "eco: oi" in corpo


def test_stream_com_limite_excedido_vira_429_antes_do_stream(cliente, monkeypatch):
    """O 429 tem que sair como status HTTP, não como evento no meio do stream."""

    async def _garantir_limite(user_id):
        raise LimiteDeMensagensExcedido("Você atingiu o limite.")

    monkeypatch.setattr(rotas.chat_service, "garantir_limite", _garantir_limite)

    r = cliente.post(f"/chats/{CHAT_ID}/messages/stream", json={"content": "oi"})

    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
