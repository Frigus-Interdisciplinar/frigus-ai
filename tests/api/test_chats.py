"""
Primeiro teste de API do repo. Não sobe Postgres/Mongo/Redis: `chat_service` é
trocado por stubs, então o que se testa é o contrato HTTP das rotas (status,
headers, body) — não o domínio, que já tem teste próprio.
"""

import pytest
from fastapi.testclient import TestClient

from frigus_ai.api.app import app
from frigus_ai.domain.errors import (
    ChatDeOutroUsuario,
    FalhaNoAgente,
    LimiteDeMensagensExcedido,
)
from frigus_ai.schemas.execution import AnswerReady, NodeStarted
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service

CHAT_ID = "chat-de-teste"


@pytest.fixture
def cliente(monkeypatch):
    async def _resolver_stock_id(user_id):
        return 1

    async def _garantir_limite(user_id):
        return None

    async def _obter_ou_criar_padrao():
        return "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"

    async def _validar_ownership(chat_id, user_id):
        """Monkeypatch: não acessa MongoDB, assume que o usuário é o dono."""
        return

    monkeypatch.setattr(user_service, "resolver_stock_id", _resolver_stock_id)
    monkeypatch.setattr(chat_service, "garantir_limite", _garantir_limite)
    monkeypatch.setattr(chat_service, "validar_ownership", _validar_ownership)
    monkeypatch.setattr(user_service, "obter_ou_criar_padrao", _obter_ou_criar_padrao)
    # raise_server_exceptions=False: o handler de `Exception` genérico
    # (api/errors/handlers.py) vira o `error_handler` do ServerErrorMiddleware, que
    # SEMPRE relança a exceção depois de montar a resposta (é assim que um servidor de
    # verdade loga o erro) — sem isso o TestClient propaga a exceção crua em vez de
    # devolver o 500 que o cliente HTTP realmente recebe.
    return TestClient(app, raise_server_exceptions=False)


def _stub_send_message(monkeypatch, erro: Exception):
    async def _falha(*args, **kwargs):
        raise erro

    monkeypatch.setattr(chat_service, "send_message", _falha)


def test_limite_de_mensagens_vira_429_com_retry_after(cliente, monkeypatch):
    _stub_send_message(monkeypatch, LimiteDeMensagensExcedido("Você atingiu o limite."))

    r = cliente.post(f"/v1/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
    assert "limite" in r.json()["detail"].lower()


def test_erro_generico_vira_500_sem_vazar_mensagem_interna(cliente, monkeypatch):
    interno = "FATAL: password authentication failed for user postgres"
    _stub_send_message(monkeypatch, RuntimeError(interno))

    r = cliente.post(f"/v1/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 500
    assert interno not in r.text
    assert r.json()["detail"] == "Erro interno inesperado."


def test_erro_de_dominio_nao_vaza_mensagem_interna(cliente, monkeypatch):
    interno = "Modelo X quebrou em http://interno:9000/segredo"
    _stub_send_message(monkeypatch, FalhaNoAgente(interno))

    r = cliente.post(f"/v1/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 502
    assert interno not in r.text
    assert r.json()["code"] == "falha_no_agente"


def test_request_id_ecoado_e_presente_no_erro(cliente, monkeypatch):
    _stub_send_message(monkeypatch, FalhaNoAgente("x"))

    r = cliente.post(f"/v1/chats/{CHAT_ID}/messages", json={"content": "oi"}, headers={"X-Request-ID": "abc-123"})

    assert r.headers["X-Request-ID"] == "abc-123"
    assert r.json()["request_id"] == "abc-123"


def test_request_id_invalido_e_substituido(cliente, monkeypatch):
    _stub_send_message(monkeypatch, FalhaNoAgente("x"))

    r = cliente.post(f"/v1/chats/{CHAT_ID}/messages", json={"content": "oi"}, headers={"X-Request-ID": "a" * 200})

    assert r.headers["X-Request-ID"] != "a" * 200
    assert r.json()["request_id"] == r.headers["X-Request-ID"]


def test_send_message_ok(cliente, monkeypatch):
    async def _ok(conteudo, chat_id, user_id, stock_id):
        return f"eco: {conteudo}"

    monkeypatch.setattr(chat_service, "send_message", _ok)

    r = cliente.post(f"/v1/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 200
    assert r.json() == {"chat_id": CHAT_ID, "content": "eco: oi"}


def test_delete_chat_devolve_202_e_agenda_encerramento(cliente, monkeypatch):
    chamadas = []

    async def _dono_ok(session_id, user_id):
        return None

    async def _encerrar(session_id, user_id):
        chamadas.append((session_id, user_id))

    monkeypatch.setattr(chat_service, "validar_ownership", _dono_ok)
    monkeypatch.setattr(chat_service, "encerrar_sessao", _encerrar)

    r = cliente.delete(f"/v1/chats/{CHAT_ID}")

    assert r.status_code == 202
    # TestClient roda as background tasks antes de devolver a resposta
    assert chamadas == [(CHAT_ID, "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")]


def test_delete_chat_de_outro_dono_vira_403_e_nao_agenda_nada(cliente, monkeypatch):
    chamadas = []

    async def _dono_errado(session_id, user_id):
        raise ChatDeOutroUsuario(session_id)

    async def _encerrar(session_id, user_id):
        chamadas.append((session_id, user_id))

    monkeypatch.setattr(chat_service, "validar_ownership", _dono_errado)
    monkeypatch.setattr(chat_service, "encerrar_sessao", _encerrar)

    r = cliente.delete(f"/v1/chats/{CHAT_ID}")

    assert r.status_code == 403
    assert chamadas == []


def test_list_chats_devolve_schema_tipado(cliente, monkeypatch):
    async def _listar(user_id):
        return [
            {
                "session_id": CHAT_ID,
                "user_id": "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c",
                "messages": [{"role": "human", "content": "oi"}],
                "resume": "conversa sobre estoque",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            }
        ]

    monkeypatch.setattr(chat_service, "listar_chats", _listar)

    r = cliente.get("/v1/chats")

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
        yield NodeStarted(node="roteador_node")
        yield NodeStarted(node="estoque_node")
        yield AnswerReady(content=f"eco: {conteudo}")

    monkeypatch.setattr(chat_service, "stream_message", _stream)

    with cliente.stream(
        "POST", f"/v1/chats/{CHAT_ID}/messages/stream", json={"content": "oi"}
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        corpo = "".join(r.iter_text())

    assert corpo.count("event: node_started") == 2
    assert "event: answer_ready" in corpo
    assert "eco: oi" in corpo


def test_stream_com_limite_excedido_vira_429_antes_do_stream(cliente, monkeypatch):
    """O 429 tem que sair como status HTTP, não como evento no meio do stream."""

    async def _garantir_limite(user_id):
        raise LimiteDeMensagensExcedido("Você atingiu o limite.")

    monkeypatch.setattr(chat_service, "garantir_limite", _garantir_limite)

    r = cliente.post(f"/v1/chats/{CHAT_ID}/messages/stream", json={"content": "oi"})

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

    monkeypatch.setattr(chat_service, "validar_ownership", _de_outro)

    resposta = cliente.post(f"/v1/chats/{CHAT_ID}/messages/stream", json={"content": "oi"})

    assert resposta.status_code == 403


def test_historico_repassa_limit_e_barra_fora_da_faixa(cliente, monkeypatch):
    async def _get_history(session_id, user_id, limit):
        _get_history.limit = limit
        return []

    monkeypatch.setattr(chat_service, "get_history", _get_history)

    assert cliente.get(f"/v1/chats/{CHAT_ID}/messages?limit=20").status_code == 200
    assert _get_history.limit == 20
    assert cliente.get(f"/v1/chats/{CHAT_ID}/messages?limit=500").status_code == 422


def test_erro_de_dominio_sem_metadata_propria_vira_500_generico(cliente, monkeypatch):
    from frigus_ai.domain.errors import SpoonacularError

    _stub_send_message(monkeypatch, SpoonacularError("chave sk-123 inválida"))

    r = cliente.post(f"/v1/chats/{CHAT_ID}/messages", json={"content": "oi"})

    assert r.status_code == 500
    assert "sk-123" not in r.text
