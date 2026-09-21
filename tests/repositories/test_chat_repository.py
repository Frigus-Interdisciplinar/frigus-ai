"""
Ownership e atomicidade do histórico de chat.

O que se protege aqui é a regra que não aparece em nenhum teste de rota: toda
operação filtra por `user_id` além do `session_id`, e o append é um upsert só —
sem o par buscar/criar que duplicava sessão sob concorrência.
"""

import pytest

import frigus_ai.repositories.chat_repository as chat_repo
from frigus_ai.repositories.chat_repository import Mensagem
from frigus_ai.schemas.models import Role


class _FakeCollection:
    """Stub mínimo do pymongo — guarda as chamadas em vez de executá-las."""

    def __init__(self, doc=None):
        self.doc = doc
        self.updates = []
        self.filtros_find = []

    def find_one(self, filtro, projecao=None):
        self.filtros_find.append(filtro)
        return self.doc

    def update_one(self, filtro, update, upsert=False):
        self.updates.append((filtro, update, upsert))

    def create_index(self, campo, unique=False):
        self.indices = (campo, unique)


@pytest.fixture
def collection(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(chat_repo, "collection", fake)
    chat_repo._garantir_indice.cache_clear()
    return fake


def _mensagens():
    return [Mensagem(role=Role.HUMAN, content="oi"), Mensagem(role=Role.AI, content="olá")]


def test_buscar_filtra_por_dono(collection):
    chat_repo._buscar_documento("sessao-1", user_id=7)

    assert collection.filtros_find == [{"session_id": "sessao-1", "user_id": 7}]


def test_adicionar_mensagens_e_um_upsert_atomico(collection):
    chat_repo._adicionar_mensagens("sessao-1", 7, _mensagens())

    assert len(collection.updates) == 1
    filtro, update, upsert = collection.updates[0]

    assert filtro == {"session_id": "sessao-1", "user_id": 7}
    assert upsert is True
    assert len(update["$push"]["messages"]["$each"]) == 2
    # created_at só no insert: um $set apagaria a data de criação a cada turno.
    assert "created_at" in update["$setOnInsert"]
    assert "updated_at" in update["$set"]


def test_indice_unico_criado_uma_vez_so(collection):
    chat_repo._adicionar_mensagens("sessao-1", 7, _mensagens())
    chat_repo._adicionar_mensagens("sessao-1", 7, _mensagens())

    assert collection.indices == ("session_id", True)


def test_inserir_resumo_filtra_por_dono(collection):
    chat_repo._inserir_resumo("resumo", "sessao-1", user_id=7)

    filtro, update, _ = collection.updates[0]
    assert filtro == {"session_id": "sessao-1", "user_id": 7}
    assert update == {"$set": {"resume": "resumo"}}


def test_buscar_documento_completo_filtra_por_dono(collection):
    """Sem o filtro por user_id, encerrar_sessao resumiria a conversa de outro usuário."""

    chat_repo._buscar_documento_completo("sessao-1", user_id=999)

    assert collection.filtros_find == [{"session_id": "sessao-1", "user_id": 999}]
