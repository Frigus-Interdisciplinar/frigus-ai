import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from frigus_ai.api.errors import register_exception_handlers
from frigus_ai.api.routes.core_chat import router
from frigus_ai.domain.errors import ChatDeOutroUsuario
from frigus_ai.domain.recipe_turn import turno_atual
from frigus_ai.graph.tools.receitas.repo import ReceitasRepo
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.repositories import identidade_repository, receitas_repository
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.settings import settings

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
SERVICE_KEY = "test-service-key-with-at-least-32-characters"
BODY = {"userId": USER_ID, "stockId": 42, "message": "O que posso cozinhar?", "foodPreferences": ["VEGAN"]}


@pytest.fixture
def cliente(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    monkeypatch.setattr(settings.api_keys, "core_service_key", SecretStr(SERVICE_KEY))
    monkeypatch.setattr(identidade_repository, "pode_acessar_estoque", lambda user, stock: user == USER_ID and stock == 42)
    monkeypatch.setattr(chat_service, "criar_chat", AsyncMock(return_value="chat-real-do-provider"))
    monkeypatch.setattr(chat_service, "validar_ownership", AsyncMock())
    return TestClient(app)


def enviar(cliente, body=None, key=SERVICE_KEY):
    return cliente.post("/internal/core/chat", json=body or BODY, headers={"X-Core-Service-Key": key})


@pytest.mark.parametrize("key", ["", "errada", "x" * 32])
def test_sem_segredo_valido_nao_cria_chat(cliente, key):
    assert enviar(cliente, key=key).status_code == 401
    chat_service.criar_chat.assert_not_awaited()


def test_rota_fechada_mesmo_no_modo_local_sem_segredo(cliente, monkeypatch):
    monkeypatch.setattr(settings.api_keys, "core_service_key", SecretStr(""))
    assert enviar(cliente).status_code == 401


def test_tool_nao_confirma_gravacao_fora_do_contexto_core():
    assert turno_atual() is None
    assert ReceitasRepo().salvar_sugestoes_receitas([7])["status"] == "error"


def test_estoque_de_outro_usuario_e_barrado_antes_do_modelo(cliente):
    assert enviar(cliente, {**BODY, "stockId": 999}).status_code == 403
    chat_service.criar_chat.assert_not_awaited()


def test_chat_de_outro_usuario_nao_pode_ser_reutilizado(cliente, monkeypatch):
    monkeypatch.setattr(chat_service, "validar_ownership", AsyncMock(side_effect=ChatDeOutroUsuario("alheio")))
    assert enviar(cliente, {**BODY, "sessionId": "alheio"}).status_code == 403
    chat_service.criar_chat.assert_not_awaited()


def test_receitas_sao_ids_consultados_e_escolhidos_no_turno_atual(cliente, monkeypatch):
    def buscar(stock, limit, **filtros):
        assert stock == 42
        assert filtros["persistir"] is False
        assert "Carne" in filtros["categorias_excluidas"]
        assert "Laticínio" in filtros["categorias_excluidas"]
        return [{"recipe_id": 7, "name": "Arroz"}, {"recipe_id": 8, "name": "Feijão"}]

    async def responder(message, session, user, stock):
        assert (user, stock, session) == (USER_ID, 42, "chat-real-do-provider")
        with session_context(user, stock):
            await asyncio.to_thread(ReceitasRepo().match_recipes_to_stock)
            assert ReceitasRepo().salvar_sugestoes_receitas([999])["status"] == "error"
            assert ReceitasRepo().salvar_sugestoes_receitas([8])["status"] == "ok"
        return "Sugiro Feijão."

    monkeypatch.setattr(receitas_repository, "match_recipes_to_stock", buscar)
    monkeypatch.setattr(chat_service, "send_message", responder)
    response = enviar(cliente)
    assert response.status_code == 200
    assert response.json() == {"sessionId": "chat-real-do-provider", "chatMessage": "Sugiro Feijão.", "recipeIds": [8]}
    assert turno_atual() is None


def test_reutiliza_sessao_sem_criar_outra_e_sem_inventar_receita(cliente, monkeypatch):
    monkeypatch.setattr(chat_service, "send_message", AsyncMock(return_value="Olá!"))
    response = enviar(cliente, {**BODY, "sessionId": "existente"})
    assert response.json()["recipeIds"] == []
    chat_service.validar_ownership.assert_awaited_once_with("existente", USER_ID)
    chat_service.criar_chat.assert_not_awaited()


@pytest.mark.parametrize("patch", [{"userId": "invalido"}, {"stockId": -1}, {"foodPreferences": ["INVENTADA"]}])
def test_contrato_invalido_nao_chega_ao_modelo(cliente, patch):
    assert enviar(cliente, {**BODY, **patch}).status_code == 422
    chat_service.criar_chat.assert_not_awaited()
