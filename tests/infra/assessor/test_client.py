"""
Cliente A2A do Assessor contra um servidor falso (`httpx.MockTransport`) — sem rede.

O que se protege: o envelope sai no formato A2A 1.0 que o Assessor publicado exige (`SendMessage`,
header `A2A-Version`, `ROLE_USER`), o mesmo chat sempre cai no mesmo `context_id`, as duas formas
de resposta (`message` e `task`) viram
texto, e qualquer falha vira `AssessorIndisponivel` em vez de estourar no grafo.
"""

import json

import httpx
import pytest
from pydantic import SecretStr

from frigus_ai.exceptions import AssessorIndisponivel
from frigus_ai.infra.assessor import client as assessor

_AsyncClientReal = httpx.AsyncClient


@pytest.fixture
def servidor(monkeypatch):
    """Configura o Assessor e troca o transporte do httpx por um handler controlado."""

    monkeypatch.setattr(assessor.settings, "ASSESSOR_A2A_URL", "http://assessor")
    monkeypatch.setattr(assessor.settings, "ASSESSOR_API_KEY", SecretStr("chave-frigus"))

    estado = {"resposta": httpx.Response(200, json={}), "requisicoes": []}

    def _handler(request):
        estado["requisicoes"].append(request)
        return estado["resposta"]

    monkeypatch.setattr(
        assessor.httpx,
        "AsyncClient",
        lambda **kw: _AsyncClientReal(transport=httpx.MockTransport(_handler), **kw),
    )
    return estado


def _message(texto):
    return {"jsonrpc": "2.0", "id": "1", "result": {"message": {
        "message_id": "m", "role": "ROLE_AGENT", "parts": [{"text": texto}],
    }}}


async def test_envelope_segue_a_spec_e_manda_a_chave(servidor):
    servidor["resposta"] = httpx.Response(200, json=_message("ok"))

    await assessor.perguntar("qual meu saldo?", "chat-1")

    [req] = servidor["requisicoes"]
    corpo = json.loads(req.content)
    mensagem = corpo["params"]["message"]

    assert str(req.url) == "http://assessor/a2a"
    assert req.headers["X-API-Key"] == "chave-frigus"
    assert req.headers["A2A-Version"] == "1.0"
    assert corpo["method"] == "SendMessage"
    assert mensagem["role"] == "ROLE_USER"
    assert mensagem["parts"] == [{"text": "qual meu saldo?"}]
    assert mensagem["context_id"] == assessor.context_id("chat-1")
    assert "message_id" in mensagem


def test_mesmo_chat_mesmo_contexto_no_assessor():
    assert assessor.context_id("chat-1") == assessor.context_id("chat-1")
    assert assessor.context_id("chat-1") != assessor.context_id("chat-2")


async def test_resposta_message_vira_texto(servidor):
    servidor["resposta"] = httpx.Response(200, json=_message("Seu saldo é R$ 1.200,00."))

    assert await assessor.perguntar("saldo?", "chat-1") == "Seu saldo é R$ 1.200,00."


async def test_resposta_task_le_os_artifacts(servidor):
    servidor["resposta"] = httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": {"task": {
        "id": "t", "context_id": "c", "status": {"state": "TASK_STATE_COMPLETED"},
        "artifacts": [{"artifact_id": "a", "parts": [{"text": "Gasto registrado."}]}],
    }}})

    assert await assessor.perguntar("registra 120 de luz", "chat-1") == "Gasto registrado."


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "error": {"code": -32603, "message": "x"}}),
        httpx.Response(500, text="erro interno"),
        httpx.Response(401, json={"detail": "API key inválida."}),
        httpx.Response(200, text="não é json"),
        httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": {"message": {"parts": []}}}),
    ],
    ids=["erro-jsonrpc", "http-500", "http-401", "corpo-nao-json", "sem-texto"],
)
async def test_falha_vira_assessor_indisponivel(servidor, resposta):
    servidor["resposta"] = resposta

    with pytest.raises(AssessorIndisponivel):
        await assessor.perguntar("saldo?", "chat-1")


async def test_sem_url_configurada_nem_tenta(monkeypatch):
    monkeypatch.setattr(assessor.settings, "ASSESSOR_A2A_URL", "")

    with pytest.raises(AssessorIndisponivel):
        await assessor.perguntar("saldo?", "chat-1")
