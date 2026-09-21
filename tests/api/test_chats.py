"""
Primeiro teste de API do repo. Não sobe Postgres/Mongo/Redis: `chat_service` é
trocado por stubs, então o que se testa é o contrato HTTP das rotas (status,
headers, body) — não o domínio, que já tem teste próprio.
"""

import pytest
from fastapi.testclient import TestClient

from frigus_ai.api.app import app
from frigus_ai.api.routes import chats as rotas
from frigus_ai.exceptions import ChatDeOutroUsuario, LimiteDeMensagensExcedido
from frigus_ai.services.user_service import user_service

CHAT_ID = "chat-de-teste"


@pytest.fixture
def cliente(monkeypatch):
    async def _iniciar_sessao(user_id):
        return 1

    async def _garantir_limite(user_id):
        return None

    async def _obter_ou_criar_padrao():
        return 1

    async def _validar_ownership(chat_id, user_id):
        """Monkeypatch: não acessa MongoDB, assume que o usuário é o dono."""
        return None

    monkeypatch.setattr(rotas.chat_service, "iniciar_sessao", _iniciar_sessao)
    monkeypatch.setattr(rotas.chat_service, "garantir_limite", _garantir_limite)
    monkeypatch.setattr(rotas.chat_service, "validar_ownership", _validar_ownership)
    monkeypatch.setattr(user_service, "obter_ou_criar_padrao", _obter_ou_criar_padrao)
    # raise_server_exceptions=False: o handler de `Exception` genérico
    # (api/exception_handler.py) vira o `error_handler` do ServerErrorMiddleware, que
    # SEMPRE relança a exceção depois de montar a resposta (é assim que um servidor de
    # verdade loga o erro) — sem isso o TestClient propaga a exceção crua em vez de
    # devolver o 500 que o cliente HTTP realmente recebe.
    return TestClient(app, raise_server_exceptions=False)


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
    assert r.json()["detail"] == "Erro interno inesperado."


def test_send_message_ok(cliente, monkeypatch):
    async def _ok(conteudo, chat_id, user_id, stock_id):
        return f"eco: {conteudo}"

    monkeypatch.setattr(rotas.chat_service, "send_message", _ok)

    r = cliente.post(f"/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 200
    assert r.json() == {"chat_id": CHAT_ID, "content": "eco: oi"}


def test_delete_chat_devolve_202_e_agenda_encerramento(cliente, monkeypatch):
    chamadas = []

    async def _dono_ok(session_id, user_id):
        return None

    async def _encerrar(session_id, user_id):
        chamadas.append((session_id, user_id))

    monkeypatch.setattr(rotas.chat_service, "validar_ownership", _dono_ok)
    monkeypatch.setattr(rotas.chat_service, "encerrar_sessao", _encerrar)

    r = cliente.delete(f"/chats/{CHAT_ID}")

    assert r.status_code == 202
    # TestClient roda as background tasks antes de devolver a resposta
    assert chamadas == [(CHAT_ID, 1)]


def test_delete_chat_de_outro_dono_vira_403_e_nao_agenda_nada(cliente, monkeypatch):
    chamadas = []

    async def _dono_errado(session_id, user_id):
        raise ChatDeOutroUsuario(session_id)

    async def _encerrar(session_id, user_id):
        chamadas.append((session_id, user_id))

    monkeypatch.setattr(rotas.chat_service, "validar_ownership", _dono_errado)
    monkeypatch.setattr(rotas.chat_service, "encerrar_sessao", _encerrar)

    r = cliente.delete(f"/chats/{CHAT_ID}")

    assert r.status_code == 403
    assert chamadas == []


def test_list_chats_devolve_schema_tipado(cliente, monkeypatch):
    async def _listar(user_id):
        return [
            {
                "session_id": CHAT_ID,
                "user_id": 1,
                "messages": [{"role": "human", "content": "oi"}],
                "resume": "conversa sobre estoque",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            }
        ]

    monkeypatch.setattr(rotas.chat_service, "listar_chats", _listar)

    r = cliente.get("/chats")

    assert r.status_code == 200
    assert r.json() == [
        {
            "chat_id": CHAT_ID,
            "resume": "conversa sobre estoque",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
        }
    ]
    # messages/user_id (internos do Mongo) não vazam no schema de resposta
    assert "messages" not in r.json()[0]


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


def test_stream_rejeita_chat_de_outro_dono(cliente, monkeypatch):
    """
    O checkpointer do grafo indexa por `thread_id=session_id` sem user_id — sem a checagem
    de dono, o /stream carregaria a conversa de outro usuário no contexto do LLM e devolveria
    pelo SSE. O `send_message` já barrava; o stream não.
    """

    async def _de_outro(session_id, user_id):
        raise ChatDeOutroUsuario(session_id)

    monkeypatch.setattr(rotas.chat_service, "validar_ownership", _de_outro)

    resposta = cliente.post(f"/chats/{CHAT_ID}/messages/stream", json={"content": "oi"})

    assert resposta.status_code == 403
