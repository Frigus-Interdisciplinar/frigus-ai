"""
Lógica do repository de preferências: conecta/desconecta relações no grafo sem
duplicar, e barra ingrediente inexistente. `User`/`Ingredient` do neomodel são
substituídos por fakes — o que se checa é o que o repository decide, não o
Cypher gerado pelo neomodel (sem bater no Neo4j de verdade).

Fakes são todos `async def`: o repository real usa `AsyncStructuredNode`/`adb`
(neomodel async nativo), não `asyncio.to_thread` em cima de chamadas síncronas.
"""

import pytest

from frigus_ai.exceptions import IngredienteNaoEncontrado
from frigus_ai.infra.neo4j.models.ingredient import Ingredient
from frigus_ai.infra.neo4j.models.user import User
from frigus_ai.repositories import preferencias_repository as repo_module
from frigus_ai.repositories.preferencias_repository import _PreferenciasNeo4jRepo


class _FakeRelManager:
    def __init__(self, conectados=None):
        self._conectados = list(conectados or [])

    async def all(self):
        return self._conectados

    async def is_connected(self, node):
        return node in self._conectados

    async def connect(self, node, properties=None):
        self._conectados.append(node)

    async def disconnect(self, node):
        self._conectados.remove(node)


class _FakeUser:
    def __init__(self, uid, prefers=None, dislikes=None, allergic_to=None):
        self.uid = uid
        self.prefers = _FakeRelManager(prefers)
        self.dislikes = _FakeRelManager(dislikes)
        self.allergic_to = _FakeRelManager(allergic_to)


class _FakeNodeSet:
    def __init__(self, resultado):
        self._resultado = resultado

    async def get(self, **_kwargs):
        return self._resultado

    async def first_or_none(self, **_kwargs):
        return self._resultado

    async def bulk_get_or_create(self, *_props, **_kwargs):
        return [self._resultado]


class _FakeUserNodeSetSemUsuario:
    """Simula `User.nodes` pra um usuário que ainda não tem node no grafo: nada a
    encontrar, e `bulk_get_or_create` cria um novo (mesmo caminho que
    `definir_preferencia` percorre na primeira preferência de um usuário novo)."""

    def __init__(self):
        self.criados: list[_FakeUser] = []

    async def first_or_none(self, **_kwargs):
        return None

    async def bulk_get_or_create(self, *props, **kwargs):
        (dados,) = props
        assert kwargs.get("merge_by") == {"keys": ["uid"]}
        novo = _FakeUser(dados["uid"])
        self.criados.append(novo)
        return [novo]


def _coentro():
    ingrediente = Ingredient()
    ingrediente.name = "Coentro"
    return ingrediente


async def test_listar_preferencias(monkeypatch):
    coentro = _coentro()
    user = _FakeUser("user-1", dislikes=[coentro], allergic_to=[coentro])
    monkeypatch.setattr(User, "nodes", _FakeNodeSet(user))

    resultado = await _PreferenciasNeo4jRepo().listar_preferencias("user-1")

    assert resultado == {"prefers": [], "dislikes": ["Coentro"], "allergic_to": ["Coentro"]}


async def test_definir_preferencia_conecta_uma_unica_vez(monkeypatch):
    coentro = _coentro()
    user = _FakeUser("user-1")
    monkeypatch.setattr(User, "nodes", _FakeNodeSet(user))
    monkeypatch.setattr(Ingredient, "nodes", _FakeNodeSet(coentro))

    repo = _PreferenciasNeo4jRepo()
    await repo.definir_preferencia("user-1", "Coentro", "dislikes")
    await repo.definir_preferencia("user-1", "Coentro", "dislikes")  # idempotente

    assert await user.dislikes.all() == [coentro]


async def test_definir_preferencia_ingrediente_inexistente_levanta_erro(monkeypatch):
    monkeypatch.setattr(User, "nodes", _FakeNodeSet(_FakeUser("user-1")))
    monkeypatch.setattr(Ingredient, "nodes", _FakeNodeSet(None))

    with pytest.raises(IngredienteNaoEncontrado):
        await _PreferenciasNeo4jRepo().definir_preferencia("user-1", "Inexistente", "prefers")


async def test_remover_preferencia(monkeypatch):
    coentro = _coentro()
    user = _FakeUser("user-1", dislikes=[coentro])
    monkeypatch.setattr(User, "nodes", _FakeNodeSet(user))
    monkeypatch.setattr(Ingredient, "nodes", _FakeNodeSet(coentro))

    await _PreferenciasNeo4jRepo().remover_preferencia("user-1", "Coentro", "dislikes")

    assert await user.dislikes.all() == []


async def test_remover_preferencia_nao_conectada_nao_falha(monkeypatch):
    coentro = _coentro()
    user = _FakeUser("user-1")
    monkeypatch.setattr(User, "nodes", _FakeNodeSet(user))
    monkeypatch.setattr(Ingredient, "nodes", _FakeNodeSet(coentro))

    await _PreferenciasNeo4jRepo().remover_preferencia("user-1", "Coentro", "dislikes")

    assert await user.dislikes.all() == []


async def test_definir_preferencia_cria_usuario_que_ainda_nao_existe_no_grafo(monkeypatch):
    """Não existe sync automático Postgres → Neo4j de usuário: a primeira preferência
    dele é que cria o node, não um cadastro prévio."""

    coentro = _coentro()
    nodes_fake = _FakeUserNodeSetSemUsuario()
    monkeypatch.setattr(User, "nodes", nodes_fake)
    monkeypatch.setattr(Ingredient, "nodes", _FakeNodeSet(coentro))

    await _PreferenciasNeo4jRepo().definir_preferencia("user-99", "Coentro", "prefers")

    assert len(nodes_fake.criados) == 1
    assert nodes_fake.criados[0].uid == "user-99"
    assert await nodes_fake.criados[0].prefers.all() == [coentro]


async def test_listar_preferencias_usuario_sem_node_devolve_vazio(monkeypatch):
    monkeypatch.setattr(User, "nodes", _FakeUserNodeSetSemUsuario())

    resultado = await _PreferenciasNeo4jRepo().listar_preferencias("user-99")

    assert resultado == {"prefers": [], "dislikes": [], "allergic_to": []}


async def test_remover_preferencia_usuario_sem_node_no_grafo_nao_falha(monkeypatch):
    monkeypatch.setattr(User, "nodes", _FakeUserNodeSetSemUsuario())

    await _PreferenciasNeo4jRepo().remover_preferencia("user-99", "Coentro", "dislikes")


async def test_receitas_sem_restricoes_monta_dicts_do_resultado_cru(monkeypatch):
    async def _cypher_query(query, params):
        assert params == {"user_id": "user-1", "limit": 5}
        return [["recipe-1", "Frango com tomate", 30, "facil"]], None

    monkeypatch.setattr(repo_module.adb, "cypher_query", _cypher_query)

    resultado = await _PreferenciasNeo4jRepo().receitas_sem_restricoes("user-1", 5)

    assert resultado == [{
        "recipe_id": "recipe-1",
        "name": "Frango com tomate",
        "preparation_time_minutes": 30,
        "difficulty": "facil",
    }]
