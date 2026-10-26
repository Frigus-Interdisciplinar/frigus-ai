"""
Invariantes de concorrência da lista de compras, checadas no SQL que o repository manda. Sessão falsa:
o efeito real (dois commits simultâneos) só se prova com Postgres, que a suíte não sobe.
"""

from contextlib import contextmanager
from datetime import date

from sqlalchemy.dialects import postgresql

from frigus_ai.infra.postgres.models import Product, ShoppingListProduct
from frigus_ai.repositories.compras_repository import _ComprasPostgresRepo


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


class _Linhas:
    def __init__(self, linhas):
        self._linhas = linhas

    def all(self):
        return self._linhas

    def one_or_none(self):
        return self._linhas[0] if self._linhas else None

    def one(self):
        return self._linhas[0]


class _Sessao:
    def __init__(self, item=None, produto=None, resultados=()):
        self.item = item
        self.produto = produto
        self.resultados = list(resultados)
        self.stmts: list = []

    def scalars(self, stmt):
        self.stmts.append(stmt)
        return self

    def first(self):
        return self.item

    def scalar(self, stmt):
        self.stmts.append(stmt)
        return "lista-1"

    def get(self, *_):
        return self.produto

    def execute(self, stmt):
        self.stmts.append(stmt)
        return self.resultados.pop(0)


class _Conn:
    def __init__(self, sessao):
        self._sessao = sessao

    @contextmanager
    def session(self):
        yield self._sessao


def test_registrar_compra_trava_a_linha_do_item():
    item = ShoppingListProduct(id=3, list_id=1, product_id=8, quantity=2, status="Pendente")
    produto = Product(id=8, name="Leite", category="Laticínio", storage_place="Geladeira", unit_price=1)
    sessao = _Sessao(item, produto, [_Linhas([(99, 5)])])

    _ComprasPostgresRepo(conn=_Conn(sessao)).registrar_compra(
        42, 3, None, date(2030, 1, 1), "Fresco", None, None
    )

    assert "FOR UPDATE OF shopping_list_products" in _sql(sessao.stmts[0])


def test_gerar_repetido_define_a_quantidade_e_nao_reabre_item_fechado():
    baixos = _Linhas([(8, "Leite", "Laticínio", 1, 4)])
    sessao = _Sessao(resultados=[baixos, _Linhas([(7, 3)])])

    itens = _ComprasPostgresRepo(conn=_Conn(sessao)).gerar_por_estoque_baixo(42)

    upsert = _sql(sessao.stmts[-1])
    assert "quantity + " not in upsert
    assert "WHERE shopping_list_products.status" in upsert
    assert itens[0]["quantity"] == 3


def test_gerar_pula_item_que_nao_esta_pendente():
    baixos = _Linhas([(8, "Leite", "Laticínio", 1, 4)])
    sessao = _Sessao(resultados=[baixos, _Linhas([])])

    assert _ComprasPostgresRepo(conn=_Conn(sessao)).gerar_por_estoque_baixo(42) == []
