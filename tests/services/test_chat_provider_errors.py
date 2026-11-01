from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from groq import BadRequestError, RateLimitError
from langchain_core.messages import HumanMessage
from openai import NotFoundError
from pydantic import SecretStr

from frigus_ai.api.errors import register_exception_handlers
from frigus_ai.api.routes.core_chat import router
from frigus_ai.domain.errors import ProvedorIAIndisponivel
from frigus_ai.graph.nodes import router as roteador
from frigus_ai.graph.state import ContextoPrompt
from frigus_ai.services import runner
from frigus_ai.services.chat_service import ChatService
from frigus_ai.services.core_chat_service import core_chat_service
from frigus_ai.settings import settings


@pytest.mark.parametrize("tipo,status", [(BadRequestError, 400), (RateLimitError, 429), (NotFoundError, 404)])
async def test_falha_do_provedor_nao_vira_estoque_vazio_nem_persiste_turno(monkeypatch, caplog, tipo, status):
    resposta = httpx.Response(status, request=httpx.Request("POST", "https://provider.example/v1/chat/completions"))
    erro = tipo("segredo-na-mensagem-do-provedor", response=resposta,
                body={"message": "segredo-na-mensagem-do-provedor"})
    chat = ChatService()
    monkeypatch.setattr(chat, "garantir_limite", AsyncMock())
    executar = AsyncMock(side_effect=erro)
    persistir = AsyncMock()
    monkeypatch.setattr(runner, "executar", executar)
    monkeypatch.setattr(chat, "_persistir_turno", persistir)

    with pytest.raises(ProvedorIAIndisponivel) as falha:
        await chat.send_message("O que tenho na geladeira?", "sessao", "usuario", 1813)

    executar.assert_awaited_once_with("O que tenho na geladeira?", "sessao", "usuario", 1813)
    persistir.assert_not_awaited()
    assert falha.value.status_code == 503
    assert "segredo-na-mensagem-do-provedor" not in caplog.text
    assert "segredo-na-mensagem-do-provedor" not in str(falha.value)


def test_core_recebe_503_identificavel_sem_payload_do_provedor(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    chave = "chave-de-teste-interna-com-mais-de-32-caracteres"
    monkeypatch.setattr(settings.api_keys, "core_service_key", SecretStr(chave))
    monkeypatch.setattr(core_chat_service, "conversar", AsyncMock(side_effect=ProvedorIAIndisponivel))

    resposta = TestClient(app).post("/internal/core/chat", headers={"X-Core-Service-Key": chave}, json={
        "userId": "123e4567-e89b-12d3-a456-426614174000", "stockId": 1813, "message": "Me sugere uma receita",
    })

    assert resposta.status_code == 503
    assert resposta.json()["code"] == "provedor_ia_indisponivel"
    assert resposta.json()["detail"] == ProvedorIAIndisponivel.public_message
    assert "Traceback" not in resposta.text


@pytest.mark.parametrize("tipo,status", [(BadRequestError, 400), (RateLimitError, 429), (NotFoundError, 404)])
async def test_provedor_fora_do_ar_no_roteador_nao_vira_resposta_de_pedido_confuso(monkeypatch, tipo, status):
    resposta = httpx.Response(status, request=httpx.Request("POST", "https://provider.example/v1/chat/completions"))
    erro = tipo("provider indisponível", response=resposta, body={"message": "indisponível"})
    monkeypatch.setattr(roteador.jev, "disponivel", lambda: False)
    modelo = SimpleNamespace(ainvoke=AsyncMock(side_effect=erro))
    monkeypatch.setattr(roteador, "router_app", modelo)

    with pytest.raises(ProvedorIAIndisponivel):
        await roteador._rotear([HumanMessage(content="Me sugere uma receita")], ContextoPrompt())

    modelo.ainvoke.assert_awaited_once()
