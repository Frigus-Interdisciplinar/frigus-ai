"""
Camada tool do financeiro: sucesso vira Response.ok, exceção vira Response.error e a
aritmética de mês/variação acontece aqui — o repository (que fala com o banco) é mockado,
a query em si é responsabilidade de repositories/financeiro_repository.py.
"""

from datetime import date

from frigus_ai.graph.tools.financeiro.repo import FinanceiroRepo, _mes_anterior
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.repositories import financeiro_repository


def _fingir(monkeypatch, nome, retorno=None, erro=None):
    def _fake(*args, **kwargs):
        if erro:
            raise erro
        return retorno

    monkeypatch.setattr(financeiro_repository, nome, _fake)


def test_mes_anterior_vira_dezembro_do_ano_passado():
    assert _mes_anterior(date(2026, 1, 15)) == "2025-12"
    assert _mes_anterior(date(2026, 3, 31)) == "2026-02"


def test_gastos_mensais_usa_o_stock_id_do_contexto(monkeypatch):
    recebido = {}

    def _gastos(stock_id, meses):
        recebido["args"] = (stock_id, list(meses))
        return {meses[0]: 150.5}

    monkeypatch.setattr(financeiro_repository, "gastos_por_mes", _gastos)

    with session_context(user_id=7, stock_id=42):
        resultado = FinanceiroRepo().gastos_mensais(mes="2026-08")

    assert recebido["args"] == (42, ["2026-08"])
    assert resultado["status"] == "ok"
    assert resultado["total_gasto"] == 150.5


def test_gastos_mensais_erro_vira_response_error(monkeypatch):
    _fingir(monkeypatch, "gastos_por_mes", erro=RuntimeError("conexão caiu"))

    with session_context(user_id=7, stock_id=42):
        resultado = FinanceiroRepo().gastos_mensais()

    assert resultado["status"] == "error"
    assert "conexão caiu" in resultado["message"]


def test_comparacao_mensal_calcula_a_variacao(monkeypatch):
    hoje = date.today()
    mes_atual, mes_anterior = hoje.strftime("%Y-%m"), _mes_anterior(hoje)

    _fingir(monkeypatch, "gastos_por_mes", {mes_atual: 150.0, mes_anterior: 100.0})

    with session_context(user_id=7, stock_id=42):
        resultado = FinanceiroRepo().comparacao_mensal()

    assert resultado["variacao_absoluta"] == 50.0
    assert resultado["variacao_percentual"] == 50.0


def test_comparacao_mensal_sem_mes_anterior_nao_divide_por_zero(monkeypatch):
    """Mês anterior zerado: percentual vira None em vez de estourar ZeroDivisionError."""

    hoje = date.today()
    mes_atual, mes_anterior = hoje.strftime("%Y-%m"), _mes_anterior(hoje)

    _fingir(monkeypatch, "gastos_por_mes", {mes_atual: 80.0, mes_anterior: 0.0})

    with session_context(user_id=7, stock_id=42):
        resultado = FinanceiroRepo().comparacao_mensal()

    assert resultado["status"] == "ok"
    assert resultado["variacao_absoluta"] == 80.0
    assert resultado["variacao_percentual"] is None


def test_valor_descartado_ok_e_erro(monkeypatch):
    _fingir(monkeypatch, "valor_descartado_do_mes", 12.75)

    with session_context(user_id=7, stock_id=42):
        assert FinanceiroRepo().valor_descartado(mes="2026-08")["valor_descartado"] == 12.75

    _fingir(monkeypatch, "valor_descartado_do_mes", erro=RuntimeError("timeout"))

    with session_context(user_id=7, stock_id=42):
        assert FinanceiroRepo().valor_descartado()["status"] == "error"


def test_evolucao_desperdicio_ok_e_erro(monkeypatch):
    _fingir(monkeypatch, "evolucao_desperdicio", [{"mes": "2026-08", "valor_descartado": 3.0}])

    with session_context(user_id=7, stock_id=42):
        resultado = FinanceiroRepo().evolucao_desperdicio(meses=3)

    assert resultado["status"] == "ok"
    assert resultado["serie"][0]["mes"] == "2026-08"

    _fingir(monkeypatch, "evolucao_desperdicio", erro=RuntimeError("timeout"))

    with session_context(user_id=7, stock_id=42):
        assert FinanceiroRepo().evolucao_desperdicio()["status"] == "error"
