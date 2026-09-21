"""
`gastos_por_mes` pede N meses numa query só, mas o Postgres devolve linha apenas para
mês que teve movimento — sem o preenchimento, um mês zerado sumiria do dict e a
`comparacao_mensal` estouraria KeyError. É a única lógica do repository que não é SQL,
então é o que dá pra checar sem banco.
"""

from contextlib import contextmanager

from frigus_ai.repositories.financeiro_repository import _FinanceiroPostgresRepo


class _FakeSession:
    def __init__(self, linhas):
        self._linhas = linhas

    def execute(self, _stmt):
        return iter(self._linhas)


class _FakeConn:
    """Imita `PostgresConn.session()` — o `@transacional` só precisa do contextmanager."""

    def __init__(self, linhas):
        self._linhas = linhas

    @contextmanager
    def session(self):
        yield _FakeSession(self._linhas)


def _repo(linhas):
    return _FinanceiroPostgresRepo(conn=_FakeConn(linhas))


def test_mes_sem_movimento_volta_zero_e_nao_some():
    gastos = _repo([("2026-08", 200)]).gastos_por_mes(42, ["2026-09", "2026-08"])

    assert gastos == {"2026-09": 0.0, "2026-08": 200.0}


def test_preserva_a_ordem_dos_meses_pedidos():
    gastos = _repo([("2026-07", 1), ("2026-09", 3)]).gastos_por_mes(
        42, ["2026-09", "2026-08", "2026-07"]
    )

    assert list(gastos) == ["2026-09", "2026-08", "2026-07"]


def test_converte_decimal_do_postgres_para_float():
    from decimal import Decimal

    gastos = _repo([("2026-08", Decimal("10.50"))]).gastos_por_mes(42, ["2026-08"])

    assert gastos["2026-08"] == 10.5
    assert isinstance(gastos["2026-08"], float)
