import pytest
from fastapi.testclient import TestClient

from frigus_ai.api.app import app
from frigus_ai.api.routes import a2a as rotas
from frigus_ai.exceptions import ChatDeOutroUsuario, LimiteDeMensagensExcedido
from frigus_ai.services.user_service import user_service


def test_agent_card_no_caminho_de_discovery_do_a2a():
    r = TestClient(app).get("/.well-known/agent-card.json")

    assert r.status_code == 200
    card = r.json()

    # O protocolo é camelCase — se sair snake_case, cliente A2A nenhum lê o card.
    assert card["protocolVersion"]
    assert card["defaultInputModes"] == ["text/plain"]
    assert {s["id"] for s in card["skills"]} == {
        "estoque", "compras", "receitas", "financeiro", "planejamento_alimentar_a2a", "faq"
    }


CHAT_ID = "sessao-a2a"


@pytest.fixture
def cliente(monkeypatch):
    async def _iniciar_sessao(user_id):
        return 1

    async def _send_message(conteudo, session_id, user_id, stock_id):
        _send_message.chamado_com = (conteudo, session_id, user_id)
        return f"eco: {conteudo}"

    async def _obter_ou_criar_padrao():
        return 1

    async def _validar_ownership(session_id, user_id):
        """Monkeypatch: não acessa MongoDB, assume que o usuário é o dono."""
        return

    monkeypatch.setattr(rotas.chat_service, "iniciar_sessao", _iniciar_sessao)
    monkeypatch.setattr(rotas.chat_service, "send_message", _send_message)
    monkeypatch.setattr(rotas.chat_service, "validar_ownership", _validar_ownership)
    monkeypatch.setattr(user_service, "obter_ou_criar_padrao", _obter_ou_criar_padrao)
    return TestClient(app), _send_message


def _rpc(metodo="message/send", params=None, id_req=1):
    return {"jsonrpc": "2.0", "id": id_req, "method": metodo, "params": params or {}}


def _mensagem(texto="oi", context_id=None):
    msg = {"kind": "message", "messageId": "m-1", "role": "user",
           "parts": [{"kind": "text", "text": texto}]}
    if context_id:
        msg["contextId"] = context_id
    return {"message": msg}


def test_message_send_responde_com_mensagem_do_agente(cliente):
    client, send_message = cliente

    r = client.post("/a2a", json=_rpc(params=_mensagem("quanto gastei?", CHAT_ID)))

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["id"] == 1
    # camelCase: em snake_case nenhum cliente A2A lê a resposta
    assert corpo["result"]["messageId"]
    assert corpo["result"]["contextId"] == CHAT_ID
    assert corpo["result"]["role"] == "agent"
    assert corpo["result"]["parts"] == [{"kind": "text", "text": "eco: quanto gastei?"}]
    assert "error" not in corpo

    # contextId do A2A é o session_id do chat — é o que mantém a conversa
    assert send_message.chamado_com == ("quanto gastei?", CHAT_ID, 1)


def test_sem_context_id_abre_sessao_nova_e_devolve_o_id(cliente):
    client, send_message = cliente

    corpo = client.post("/a2a", json=_rpc(params=_mensagem())).json()

    gerado = corpo["result"]["contextId"]
    assert gerado
    assert send_message.chamado_com[1] == gerado


def test_context_id_de_outro_usuario_vira_403(cliente, monkeypatch):
    """contextId é controlado por quem chama — sem checar dono, o A2A deixa
    qualquer chamador entrar na sessão de outro usuário via `session_id`."""

    client, _ = cliente

    async def _de_outro(session_id, user_id):
        raise ChatDeOutroUsuario(session_id)

    monkeypatch.setattr(rotas.chat_service, "validar_ownership", _de_outro)

    r = client.post("/a2a", json=_rpc(params=_mensagem("oi", CHAT_ID)))

    assert r.status_code == 403


def test_metodo_nao_suportado_vira_erro_jsonrpc_e_nao_500(cliente):
    client, _ = cliente

    r = client.post("/a2a", json=_rpc(metodo="message/stream", params=_mensagem()))

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["error"]["code"] == -32601
    # JSON-RPC proíbe result e error juntos
    assert "result" not in corpo


def test_params_invalidos_viram_32602(cliente):
    client, _ = cliente

    r = client.post("/a2a", json=_rpc(params={"message": {"role": "user"}}))

    assert r.status_code == 200
    assert r.json()["error"]["code"] == -32602


def test_rate_limit_vira_429_de_transporte(cliente, monkeypatch):
    client, _ = cliente

    async def _estourou(*args, **kwargs):
        raise LimiteDeMensagensExcedido("Você atingiu o limite.")

    monkeypatch.setattr(rotas.chat_service, "send_message", _estourou)

    r = client.post("/a2a", json=_rpc(params=_mensagem()))

    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"


def test_url_do_card_aponta_pro_endpoint_que_existe(cliente):
    """O card anuncia o `url` de invocação — se ele apontar pro vazio, o A2A é fachada."""

    client, _ = cliente
    card = client.get("/.well-known/agent-card.json").json()

    caminho = card["url"].removeprefix(rotas.settings.A2A_BASE_URL)
    assert client.post(caminho, json=_rpc(params=_mensagem())).status_code == 200
