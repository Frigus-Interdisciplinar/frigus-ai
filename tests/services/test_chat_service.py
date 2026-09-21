"""
Orquestração de `ChatService.encerrar_sessao`: resumir e atualizar o perfil só quando
a sessão teve mensagem de verdade, sem bater no LLM/Mongo real (repository e
user_service são mockados; a query em si já tem teste próprio em
tests/repositories/test_chat_repository.py).
"""

from frigus_ai.repositories import chat_repository
from frigus_ai.services import chat_service as chat_service_module
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service


async def test_encerrar_sessao_sem_mensagens_nao_gera_resumo(monkeypatch):
    async def _buscar_documento_completo(session_id, user_id):
        return None

    chamou_resumo = []
    monkeypatch.setattr(chat_repository, "buscar_documento_completo", _buscar_documento_completo)
    monkeypatch.setattr(chat_service_module, "_gerar_resumo", lambda msgs: chamou_resumo.append(msgs) or "x")

    invalidou = []

    async def _invalidar_perfil_cache(user_id):
        invalidou.append(user_id)

    monkeypatch.setattr(user_service, "invalidar_perfil_cache", _invalidar_perfil_cache)

    await chat_service.encerrar_sessao("sessao-1", user_id=7)

    assert chamou_resumo == []
    assert invalidou == [7]


async def test_encerrar_sessao_com_mensagens_resume_e_atualiza_perfil(monkeypatch):
    async def _buscar_documento_completo(session_id, user_id):
        return {"messages": [{"role": "human", "content": "oi"}]}

    monkeypatch.setattr(chat_repository, "buscar_documento_completo", _buscar_documento_completo)
    monkeypatch.setattr(chat_service_module, "_gerar_resumo", lambda msgs: "resumo da conversa")

    salvou_resumo = []

    async def _salvar_resumo(resumo, session_id, user_id):
        salvou_resumo.append((resumo, session_id, user_id))

    monkeypatch.setattr(chat_repository, "salvar_resumo", _salvar_resumo)

    atualizou_perfil = []

    async def _atualizar_perfil_pelo_resumo(user_id, resumo):
        atualizou_perfil.append((user_id, resumo))

    monkeypatch.setattr(user_service, "atualizar_perfil_pelo_resumo", _atualizar_perfil_pelo_resumo)

    invalidou = []

    async def _invalidar_perfil_cache(user_id):
        invalidou.append(user_id)

    monkeypatch.setattr(user_service, "invalidar_perfil_cache", _invalidar_perfil_cache)

    await chat_service.encerrar_sessao("sessao-1", user_id=7)

    assert salvou_resumo == [("resumo da conversa", "sessao-1", 7)]
    assert atualizou_perfil == [(7, "resumo da conversa")]
    assert invalidou == [7]
