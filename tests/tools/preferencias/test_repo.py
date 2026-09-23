"""
Camada tool de preferências: sucesso vira Response.ok, exceção vira Response.error —
sem bater no Neo4j de verdade (o repository, que fala com o grafo, é mockado; a
query em si é responsabilidade de repositories/preferencias_repository.py).
"""

from frigus_ai.graph.tools.preferencias.repo import PreferenciasRepo
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.repositories import preferencias_repository


async def test_listar_preferencias_usa_o_uid_derivado_do_user_id_do_contexto(monkeypatch):
    chamado_com = {}

    async def _listar(user_id):
        chamado_com["user_id"] = user_id
        return {"prefers": ["Frango"], "dislikes": ["Coentro"], "allergic_to": ["Coentro"]}

    monkeypatch.setattr(preferencias_repository, "listar_preferencias", _listar)

    with session_context(user_id=1, stock_id=None):
        resultado = await PreferenciasRepo().listar_preferencias()

    assert chamado_com["user_id"] == "user-1"
    assert resultado["status"] == "ok"
    assert resultado["prefers"] == ["Frango"]


async def test_listar_preferencias_erro_vira_response_error(monkeypatch):
    async def _falha(user_id):
        raise RuntimeError("conexão caiu")

    monkeypatch.setattr(preferencias_repository, "listar_preferencias", _falha)

    with session_context(user_id=1, stock_id=None):
        resultado = await PreferenciasRepo().listar_preferencias()

    assert resultado["status"] == "error"
    assert "conexão caiu" in resultado["message"]


async def test_definir_preferencia_ok(monkeypatch):
    chamado_com = {}

    async def _definir(user_id, ingrediente_nome, tipo):
        chamado_com["args"] = (user_id, ingrediente_nome, tipo)

    monkeypatch.setattr(preferencias_repository, "definir_preferencia", _definir)

    with session_context(user_id=1, stock_id=None):
        resultado = await PreferenciasRepo().definir_preferencia("Tomate", "prefers")

    assert chamado_com["args"] == ("user-1", "Tomate", "prefers")
    assert resultado["status"] == "ok"
    assert resultado["ingrediente_nome"] == "Tomate"
    assert resultado["tipo"] == "prefers"


async def test_definir_preferencia_ingrediente_nao_encontrado_vira_response_error(monkeypatch):
    from frigus_ai.exceptions import IngredienteNaoEncontrado

    async def _falha(user_id, ingrediente_nome, tipo):
        raise IngredienteNaoEncontrado(ingrediente_nome)

    monkeypatch.setattr(preferencias_repository, "definir_preferencia", _falha)

    with session_context(user_id=1, stock_id=None):
        resultado = await PreferenciasRepo().definir_preferencia("Inexistente", "prefers")

    assert resultado["status"] == "error"
    assert "Inexistente" in resultado["message"]


async def test_remover_preferencia_ok(monkeypatch):
    chamado_com = {}

    async def _remover(user_id, ingrediente_nome, tipo):
        chamado_com["args"] = (user_id, ingrediente_nome, tipo)

    monkeypatch.setattr(preferencias_repository, "remover_preferencia", _remover)

    with session_context(user_id=1, stock_id=None):
        resultado = await PreferenciasRepo().remover_preferencia("Coentro", "dislikes")

    assert chamado_com["args"] == ("user-1", "Coentro", "dislikes")
    assert resultado["status"] == "ok"


async def test_sugerir_receitas_compativeis_usa_o_uid_derivado_do_user_id_do_contexto(monkeypatch):
    chamado_com = {}

    async def _receitas(user_id, limit):
        chamado_com["args"] = (user_id, limit)
        return [{"recipe_id": "recipe-1", "name": "Frango com tomate",
                  "preparation_time_minutes": 30, "difficulty": "facil"}]

    monkeypatch.setattr(preferencias_repository, "receitas_sem_restricoes", _receitas)

    with session_context(user_id=1, stock_id=None):
        resultado = await PreferenciasRepo().sugerir_receitas_compativeis(limit=5)

    assert chamado_com["args"] == ("user-1", 5)
    assert resultado["status"] == "ok"
    assert resultado["total_records"] == 1
    assert resultado["receitas"][0]["name"] == "Frango com tomate"
