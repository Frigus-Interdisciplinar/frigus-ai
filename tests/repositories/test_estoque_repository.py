"""
A lógica do repository de estoque que não é SQL: derivar o tipo de movimento, barrar
quantidade negativa e — o acoplamento mais frágil do projeto — gravar a saída do descarte
com a MESMA data do `discard`, que é como `financeiro_repository` casa os dois pra
calcular o valor desperdiçado.

Sessão falsa, sem banco: o que se checa é o que o repository decide e o que ele manda
persistir, não o SQL gerado.
"""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from frigus_ai.exceptions import ItemDeEstoqueNaoEncontrado, QuantidadeNegativa
from frigus_ai.infra.postgres.models import Discard, StockMovement, StockProduct
from frigus_ai.repositories.estoque_repository import _EstoquePostgresRepo

DATA_DO_DESCARTE = datetime(2026, 8, 20, 10, 30, tzinfo=UTC)


class _FakeSession:
    def __init__(self, item, product_name="Leite"):
        self._item = item
        self._product_name = product_name
        self.adicionados: list = []

    def scalars(self, _stmt):
        return self

    def first(self):
        return self._item

    def scalar(self, stmt):
        # Só dois formatos de `select` passam por `.scalar()` aqui: o lookup de nome do
        # produto (descartar) e o `proximo_id` -> COALESCE(MAX(id), 0). Distingue pela
        # coluna selecionada, não pela ordem de chamada.
        if list(stmt.selected_columns.keys()) == ["name"]:
            return self._product_name
        return 0

    def add(self, obj):
        self.adicionados.append(obj)

    def flush(self):
        pass

    def refresh(self, obj):
        if isinstance(obj, Discard):
            obj.date = DATA_DO_DESCARTE

    def movimentos(self):
        return [o for o in self.adicionados if isinstance(o, StockMovement)]

    def descartes(self):
        return [o for o in self.adicionados if isinstance(o, Discard)]


class _FakeConn:
    def __init__(self, sessao):
        self._sessao = sessao

    @contextmanager
    def session(self):
        yield self._sessao


def _repo(item):
    sessao = _FakeSession(item)
    return _EstoquePostgresRepo(conn=_FakeConn(sessao)), sessao


def _item(quantidade: int) -> StockProduct:
    return StockProduct(id=5, product_id=1, stock_id=42, quantity=quantidade)


@pytest.mark.parametrize(
    ("delta", "novo_valor", "tipo_esperado", "quantidade_esperada", "movimento_esperado"),
    [
        (-3,   None, "Saída",   7, 3),   # consumo
        (4,    None, "Entrada", 14, 4),  # reposição
        (None, 2,    "Ajuste",  2, 8),   # correção: 10 -> 2, movimento registra |variação|
        (None, 25,   "Ajuste",  25, 15),
    ],
)
def test_deriva_tipo_de_movimento(
    delta, novo_valor, tipo_esperado, quantidade_esperada, movimento_esperado
):
    repo, sessao = _repo(_item(10))

    item_id, final = repo.atualizar_quantidade(42, 7, 5, None, delta, novo_valor)

    assert (item_id, final) == (5, quantidade_esperada)

    (movimento,) = sessao.movimentos()
    assert movimento.movement_type == tipo_esperado
    assert movimento.quantity == movimento_esperado  # sempre positivo
    assert movimento.user_id == 7


def test_quantidade_final_negativa_e_barrada_antes_de_gravar():
    repo, sessao = _repo(_item(2))

    with pytest.raises(QuantidadeNegativa):
        repo.atualizar_quantidade(42, 7, 5, None, -5, None)

    assert sessao.movimentos() == []  # nada foi persistido


def test_item_inexistente_levanta_domain_error():
    repo, _ = _repo(None)

    with pytest.raises(ItemDeEstoqueNaoEncontrado):
        repo.atualizar_quantidade(42, 7, 5, None, -1, None)


def test_sem_id_nem_nome_nao_varre_o_estoque_inteiro():
    """Sem filtro nenhum, `_localizar` pegaria um item qualquer do estoque — tem que falhar."""

    repo, _ = _repo(_item(10))

    with pytest.raises(ItemDeEstoqueNaoEncontrado):
        repo.atualizar_quantidade(42, 7, None, None, -1, None)


def test_descarte_grava_a_saida_com_a_data_do_discard():
    """
    Acoplamento com o financeiro: o join é por (stock_product_id, date). Se a saída for
    gravada com outra data (ou sem data), o valor desperdiçado vira zero silenciosamente.
    """

    repo, sessao = _repo(_item(4))

    resultado = repo.descartar(42, 7, 5, None, "Estragado")
    assert resultado == {
        "stock_product_id": 5, "product_name": "Leite", "quantidade_perdida": 4
    }

    (descarte,) = sessao.descartes()
    (movimento,) = sessao.movimentos()

    assert descarte.reason == "Estragado"
    assert movimento.movement_type == "Saída"
    assert movimento.quantity == 4
    assert movimento.date == DATA_DO_DESCARTE == descarte.date


def test_descarte_zera_o_item_e_marca_vencido():
    repo, sessao = _repo(_item(4))

    repo.descartar(42, 7, 5, None, "Vencido")

    assert sessao._item.quantity == 0
    assert sessao._item.product_status == "Vencido"


def test_descarte_de_item_zerado_nao_gera_movimento():
    """Item já sem quantidade não tem volume perdido a registrar — só o descarte."""

    repo, sessao = _repo(_item(0))

    repo.descartar(42, 7, 5, None, "Vencido")

    assert sessao.descartes() != []
    assert sessao.movimentos() == []
