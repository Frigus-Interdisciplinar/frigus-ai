"""
Ownership e atomicidade do histórico de chat.

O que se protege aqui é a regra que não aparece em nenhum teste de rota: toda
operação filtra por `user_id` além do `session_id`, e o append é um upsert só —
sem o par buscar/criar que duplicava sessão sob concorrência.
"""

import pytest

import frigus_ai.tools.mongo.chats.core as chats
from frigus_ai.tools.mongo.chats.schemas import Mensagem, Role


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
    monkeypatch.setattr(chats, "collection", fake)
    chats._garantir_indice.cache_clear()
    return fake


def _mensagens():
    return [Mensagem(role=Role.HUMAN, content="oi"), Mensagem(role=Role.AI, content="olá")]


def test_buscar_filtra_por_dono(collection):
    chats.buscar("sessao-1", user_id=7)

    assert collection.filtros_find == [{"session_id": "sessao-1", "user_id": 7}]


def test_adicionar_mensagens_e_um_upsert_atomico(collection):
    chats.adicionar_mensagens("sessao-1", 7, _mensagens())

    assert len(collection.updates) == 1
    filtro, update, upsert = collection.updates[0]

    assert filtro == {"session_id": "sessao-1", "user_id": 7}
    assert upsert is True
    assert len(update["$push"]["messages"]["$each"]) == 2
    # created_at só no insert: um $set apagaria a data de criação a cada turno.
    assert "created_at" in update["$setOnInsert"]
    assert "updated_at" in update["$set"]


def test_indice_unico_criado_uma_vez_so(collection):
    chats.adicionar_mensagens("sessao-1", 7, _mensagens())
    chats.adicionar_mensagens("sessao-1", 7, _mensagens())

    assert collection.indices == ("session_id", True)


def test_inserir_resumo_filtra_por_dono(collection):
    chats.inserir_resumo("resumo", "sessao-1", user_id=7)

    filtro, update, _ = collection.updates[0]
    assert filtro == {"session_id": "sessao-1", "user_id": 7}
    assert update == {"$set": {"resume": "resumo"}}


def test_encerrar_sessao_de_outro_dono_nao_gera_resumo(collection, monkeypatch):
    """Sem o filtro por user_id isso viraria resumo (e perfil) da conversa alheia."""

    chamou = []
    monkeypatch.setattr(chats, "_gerar_resumo", lambda msgs: chamou.append(msgs) or "x")

    collection.doc = None  # find_one com o filtro do dono errado não acha nada
    chats.encerrar_sessao("sessao-1", user_id=999)

    assert chamou == []
    assert collection.filtros_find == [{"session_id": "sessao-1", "user_id": 999}]
