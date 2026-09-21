"""
Camada tool de compras: sucesso vira Response.ok, exceção vira Response.error — o
repository (que fala com o banco) é mockado, a query em si é responsabilidade de
repositories/compras_repository.py.
"""

from frigus_ai.graph.tools.compras.repo import ComprasRepo
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.repositories import compras_repository


def _fingir(monkeypatch, nome, retorno=None, erro=None):
    def _fake(*args, **kwargs):
        if erro:
            raise erro
        return retorno

    monkeypatch.setattr(compras_repository, nome, _fake)


def test_create_shopping_list_ok(monkeypatch):
    _fingir(monkeypatch, "criar_lista_aberta", 7)

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().create_shopping_list()

    assert resultado["status"] == "ok"
    assert resultado["shopping_list_id"] == 7


def test_create_shopping_list_erro_vira_response_error(monkeypatch):
    _fingir(monkeypatch, "criar_lista_aberta", erro=RuntimeError("conexão caiu"))

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().create_shopping_list()

    assert resultado["status"] == "error"
    assert "conexão caiu" in resultado["message"]


def test_add_shopping_list_product_usa_o_stock_id_do_contexto(monkeypatch):
    recebido = {}

    def _adicionar(stock_id, product_name, category, storage_place, quantity):
        recebido["args"] = (stock_id, product_name, category, storage_place, quantity)
        return (10, quantity)

    monkeypatch.setattr(compras_repository, "adicionar_item", _adicionar)

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().add_shopping_list_product(
            product_name="Arroz", category="Grão", storage_place="Despensa", quantity=2
        )

    assert recebido["args"] == (42, "Arroz", "Grão", "Despensa", 2)
    assert resultado["status"] == "ok"
    assert resultado["shopping_list_product_id"] == 10
    assert resultado["quantity"] == 2


def test_add_shopping_list_product_sem_categoria_vira_response_error(monkeypatch):
    from frigus_ai.exceptions import ProdutoNaoCadastrado

    _fingir(monkeypatch, "adicionar_item", erro=ProdutoNaoCadastrado())

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().add_shopping_list_product(
            product_name="Produto novo", category="", storage_place="", quantity=1
        )

    assert resultado["status"] == "error"
    assert "catálogo" in resultado["message"]


def test_query_shopping_list_ok(monkeypatch):
    _fingir(
        monkeypatch,
        "consultar_lista",
        [{"shopping_list_product_id": 1, "product_name": "Arroz", "category": "Grão",
          "quantity": 2, "status": "Pendente"}],
    )

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().query_shopping_list()

    assert resultado["status"] == "ok"
    assert resultado["total_records"] == 1


def test_mark_purchased_sem_identificador_nao_chama_repositorio(monkeypatch):
    chamado = []
    monkeypatch.setattr(
        compras_repository, "marcar_status", lambda *a, **kw: chamado.append(1) or 1
    )

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().mark_purchased()

    assert resultado["status"] == "error"
    assert chamado == []


def test_mark_purchased_item_nao_encontrado_vira_response_error(monkeypatch):
    from frigus_ai.exceptions import ItemDeCompraNaoEncontrado

    _fingir(monkeypatch, "marcar_status", erro=ItemDeCompraNaoEncontrado())

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().mark_purchased(shopping_list_product_id=999)

    assert resultado["status"] == "error"


def test_generate_shopping_list_from_low_stock_ok(monkeypatch):
    _fingir(
        monkeypatch,
        "gerar_por_estoque_baixo",
        [{"shopping_list_product_id": 1, "product_name": "Leite", "category": "Laticínio",
          "quantity": 3, "status": "Pendente"}],
    )

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().generate_shopping_list_from_low_stock()

    assert resultado["status"] == "ok"
    assert resultado["total_adicionados"] == 1


def test_generate_shopping_list_from_low_stock_sem_itens_baixos(monkeypatch):
    _fingir(monkeypatch, "gerar_por_estoque_baixo", [])

    with session_context(user_id=1, stock_id=42):
        resultado = ComprasRepo().generate_shopping_list_from_low_stock()

    assert resultado["status"] == "ok"
    assert resultado["total_adicionados"] == 0
