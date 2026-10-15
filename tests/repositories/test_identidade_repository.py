"""
Bootstrap de identidade no 1º login. O que importa aqui é a corrida: o app dispara várias requisições
juntas, todas veem que o email não existe, e só uma pode inserir (email é único). A que perde precisa
devolver o usuário da vencedora, sem tentar criar grupo/estoque de novo.

Sessão falsa, sem banco: o que se checa é o que o repository decide e manda persistir.
"""

from contextlib import contextmanager

from sqlalchemy.dialects import postgresql

from frigus_ai.infra.postgres.models import Group, Stock, UserGroup
from frigus_ai.repositories.identidade_repository import _IdentidadeRepo


class _FakeSession:
    def __init__(self, *respostas):
        self._respostas = list(respostas)
        self.consultas: list = []
        self.adicionados: list = []

    def scalar(self, stmt):
        self.consultas.append(stmt)
        return self._respostas.pop(0)

    def add(self, obj):
        self.adicionados.append(obj)

    def flush(self):
        pass


class _FakeConn:
    def __init__(self, sessao):
        self._sessao = sessao

    @contextmanager
    def session(self):
        yield self._sessao


def _criar(sessao):
    return _IdentidadeRepo(conn=_FakeConn(sessao)).criar_usuario("Ana", "ana@frigus.com")


def test_usuario_existente_e_devolvido_sem_inserir_nada():
    sessao = _FakeSession("uuid-existente")

    assert _criar(sessao) == "uuid-existente"
    assert len(sessao.consultas) == 1
    assert sessao.adicionados == []


def test_usuario_novo_ganha_grupo_estoque_e_vinculo():
    sessao = _FakeSession(None, "uuid-novo")

    assert _criar(sessao) == "uuid-novo"
    assert [type(o) for o in sessao.adicionados] == [Group, Stock, UserGroup]
    assert sessao.adicionados[0].owner_id == "uuid-novo"


def test_perder_a_corrida_devolve_o_usuario_da_vencedora_sem_criar_grupo():
    sessao = _FakeSession(None, None, "uuid-da-vencedora")

    assert _criar(sessao) == "uuid-da-vencedora"
    assert sessao.adicionados == []


def test_insercao_ignora_conflito_de_email():
    sessao = _FakeSession(None, "uuid-novo")
    _criar(sessao)

    sql = str(sessao.consultas[1].compile(dialect=postgresql.dialect()))

    assert "ON CONFLICT (email) WHERE deleted_at IS NULL DO NOTHING" in sql
    assert "RETURNING users.id" in sql
    assert "users.deleted_at IS NULL" in str(sessao.consultas[0].compile(dialect=postgresql.dialect()))
