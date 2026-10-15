"""
Camada tool de preferências: as alergias vêm do perfil (Mongo, via user_service) e
somam com o `evitar` do LLM antes de ir pro grafo. Repository e user_service são
mockados — sem bater no Neo4j nem no Mongo de verdade.
"""

from frigus_ai.domain.models import Fatos
from frigus_ai.graph.tools.preferencias import repo as tool_module
from frigus_ai.graph.tools.preferencias.repo import PreferenciasRepo
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.repositories import preferencias_repository

USER_ID = "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"


def _mockar(monkeypatch, alergias, chamado_com):
    async def _fatos(user_id):
        chamado_com["user_id"] = user_id
        return Fatos(alergias=alergias)

    async def _receitas(evitar, limit):
        chamado_com["args"] = (evitar, limit)
        return [{"recipe_id": "recipe-1", "name": "Frango com tomate",
                 "preparation_time_minutes": 30, "difficulty": "facil"}]

    monkeypatch.setattr(tool_module.user_service, "buscar_fatos", _fatos)
    monkeypatch.setattr(preferencias_repository, "receitas_sem_ingredientes", _receitas)


async def test_sugerir_receitas_soma_alergias_do_perfil_com_evitar(monkeypatch):
    chamado_com = {}
    _mockar(monkeypatch, ["Camarão", "Amendoim (filho)"], chamado_com)

    with session_context(user_id=USER_ID, stock_id=None):
        resultado = await PreferenciasRepo().sugerir_receitas_compativeis(evitar=["Coentro"], limit=5)

    assert chamado_com["user_id"] == USER_ID
    assert chamado_com["args"] == (["Camarão", "Amendoim", "Coentro"], 5)
    assert resultado["status"] == "ok"
    assert resultado["total_records"] == 1


async def test_sugerir_receitas_sem_evitar_usa_so_alergias(monkeypatch):
    chamado_com = {}
    _mockar(monkeypatch, ["Lactose"], chamado_com)

    with session_context(user_id=USER_ID, stock_id=None):
        await PreferenciasRepo().sugerir_receitas_compativeis()

    assert chamado_com["args"] == (["Lactose"], 10)


async def test_sugerir_receitas_erro_vira_response_error(monkeypatch):
    async def _falha(user_id):
        raise RuntimeError("mongo fora")

    monkeypatch.setattr(tool_module.user_service, "buscar_fatos", _falha)

    with session_context(user_id=USER_ID, stock_id=None):
        resultado = await PreferenciasRepo().sugerir_receitas_compativeis()

    assert resultado["status"] == "error"
