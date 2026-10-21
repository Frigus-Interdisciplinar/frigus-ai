"""
`registrar_compra`: a entrada no estoque e o status `Comprado` saem juntos, e o item que já foi
comprado não soma de novo. Sessão falsa, sem banco: checa o que o repository decide e manda gravar.
"""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest

from frigus_ai.infra.postgres.models import Product, ShoppingListProduct
from frigus_ai.repositories.compras_repository import _ComprasPostgresRepo

VALIDADE = date(2026, 12, 1)


class _Resultado:
    def one(self):
        return (99, 5)


class _FakeSession:
    def __init__(self, item, produto):
        self._item = item
        self._produto = produto
        self.comandos: list = []

    def scalars(self, _stmt):
        return self

    def first(self):
        return self._item

    def get(self, _modelo, _id):
        return self._produto

    def execute(self, stmt):
        self.comandos.append(stmt)
        return _Resultado()


class _FakeConn:
    def __init__(self, sessao):
        self._sessao = sessao

    @contextmanager
    def session(self):
        yield self._sessao


def _repo(status="Pendente", preco=0):
    item = ShoppingListProduct(id=3, list_id=1, product_id=8, quantity=2, status=status)
    produto = Product(id=8, name="Leite", category="Laticínio", storage_place="Geladeira", unit_price=Decimal(preco))
    sessao = _FakeSession(item, produto)
    return _ComprasPostgresRepo(conn=_FakeConn(sessao)), sessao, item, produto


def test_compra_da_entrada_no_estoque_e_marca_o_item_como_comprado():
    repo, sessao, item, _ = _repo()

    resultado = repo.registrar_compra(42, 3, None, VALIDADE, "Fresco", None, None)

    assert resultado == (99, 5)
    assert item.status == "Comprado"
    (insert,) = sessao.comandos
    assert insert.compile().params["quantity"] == 2  # sem quantidade informada, vale a da lista


def test_quantidade_informada_vale_mais_que_a_da_lista():
    repo, sessao, _, _ = _repo()

    repo.registrar_compra(42, 3, None, VALIDADE, "Fresco", 6, None)

    assert sessao.comandos[0].compile().params["quantity"] == 6


def test_preco_pago_preenche_o_catalogo_so_quando_ele_estava_zerado():
    repo, _, _, produto = _repo(preco=0)
    repo.registrar_compra(42, 3, None, VALIDADE, "Fresco", None, 7.5)
    assert produto.unit_price == Decimal("7.5")

    repo, _, _, produto = _repo(preco=4)
    repo.registrar_compra(42, 3, None, VALIDADE, "Fresco", None, 7.5)
    assert produto.unit_price == Decimal(4)


def test_item_ja_comprado_nao_soma_estoque_de_novo():
    repo, sessao, _, _ = _repo(status="Comprado")

    with pytest.raises(ValueError, match="já foi marcado como comprado"):
        repo.registrar_compra(42, 3, None, VALIDADE, "Fresco", None, None)

    assert sessao.comandos == []
