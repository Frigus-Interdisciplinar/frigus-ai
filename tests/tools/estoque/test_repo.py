"""
Camada tool do estoque: normaliza a entrada do LLM, chama o repository e traduz para
`Response`. O repository (que fala com o Postgres) é mockado — a query em si é
responsabilidade de repositories/estoque_repository.py.
"""

from datetime import date, timedelta

import pytest

from frigus_ai.domain.errors import ItemDeEstoqueNaoEncontrado, QuantidadeNegativa
from frigus_ai.graph.tools.estoque import repo as repo_mod
from frigus_ai.graph.tools.estoque.repo import EstoqueRepo
from frigus_ai.graph.tools.estoque.resolver import NomeAmbiguo
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.repositories import estoque_repository

CONTEXTO = {"user_id": 7, "stock_id": 42}


@pytest.fixture(autouse=True)
def _sem_resolucao_de_nome(monkeypatch):
    """O resolvedor tem teste próprio; aqui o nome segue direto pro repository, como antes."""

    monkeypatch.setattr(repo_mod, "resolver_item", lambda stock_id, nome: None)


def _fingir(monkeypatch, nome, retorno=None, erro=None, captura=None):
    def _fake(*args, **kwargs):
        if captura is not None:
            captura["args"] = args
        if erro:
            raise erro
        return retorno

    monkeypatch.setattr(estoque_repository, nome, _fake)


def test_add_stock_product_calcula_o_status_e_repassa_normalizado(monkeypatch):
    captura: dict = {}
    _fingir(monkeypatch, "adicionar_produto", retorno=(10, 5), captura=captura)

    daqui_um_ano = (date.today() + timedelta(days=365)).isoformat()

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().add_stock_product(
            product_name="Leite", category="Laticínio", storage_place="Geladeira",
            quantity=5, expire_date=daqui_um_ano, unit_price=4.5,
        )

    stock_id, dados = captura["args"]
    assert stock_id == 42
    assert dados["product_status"] == "Fresco"          # validade longe -> semáforo verde
    assert dados["expire_date"] == date.fromisoformat(daqui_um_ano)
    assert resultado["status"] == "ok"
    assert resultado["stock_product_id"] == 10
    assert resultado["quantity"] == 5


def test_add_stock_product_marca_vencido_para_data_passada(monkeypatch):
    captura: dict = {}
    _fingir(monkeypatch, "adicionar_produto", retorno=(11, 1), captura=captura)

    with session_context(**CONTEXTO):
        EstoqueRepo().add_stock_product(
            product_name="Iogurte", category="Laticínio", storage_place="Geladeira",
            quantity=1, expire_date=(date.today() - timedelta(days=3)).isoformat(),
        )

    assert captura["args"][1]["product_status"] == "Vencido"


def test_add_stock_product_data_invalida_vira_response_error(monkeypatch):
    _fingir(monkeypatch, "adicionar_produto", retorno=(1, 1))

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().add_stock_product(
            product_name="Leite", category="Laticínio", storage_place="Geladeira",
            quantity=1, expire_date="ontem",
        )

    assert resultado["status"] == "error"


def test_query_stock_converte_vencendo_em_dias_em_data_limite(monkeypatch):
    captura: dict = {}
    _fingir(monkeypatch, "consultar_estoque", retorno=[], captura=captura)

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().query_stock(vencendo_em_dias=3, storage_place="Geladeira")

    _, filtros = captura["args"]
    assert filtros["vence_ate"] == date.today() + timedelta(days=3)
    assert filtros["storage_place"] == "Geladeira"
    assert resultado["total_records"] == 0


def test_query_stock_sem_vencendo_em_dias_nao_filtra_por_data(monkeypatch):
    captura: dict = {}
    _fingir(monkeypatch, "consultar_estoque", retorno=[], captura=captura)

    with session_context(**CONTEXTO):
        EstoqueRepo().query_stock()

    assert captura["args"][1]["vence_ate"] is None


def test_update_sem_delta_nem_novo_valor_nem_chega_no_banco(monkeypatch):
    def _nao_deveria(*args, **kwargs):
        raise AssertionError("não deveria chamar o repository")

    monkeypatch.setattr(estoque_repository, "atualizar_quantidade", _nao_deveria)

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().update_stock_quantity(stock_product_id=1)

    assert resultado["status"] == "error"
    assert "delta" in resultado["message"]


def test_update_repassa_contexto_e_devolve_a_quantidade_final(monkeypatch):
    captura: dict = {}
    _fingir(monkeypatch, "atualizar_quantidade", retorno=(5, 2), captura=captura)

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().update_stock_quantity(stock_product_id=5, delta=-3)

    stock_id, user_id, item_id, nome, delta, novo_valor = captura["args"]
    assert (stock_id, user_id) == (42, 7)
    assert (item_id, nome, delta, novo_valor) == (5, None, -3, None)
    assert resultado["quantity"] == 2


def test_update_item_inexistente_preserva_a_mensagem_de_dominio(monkeypatch):
    _fingir(monkeypatch, "atualizar_quantidade", erro=ItemDeEstoqueNaoEncontrado())

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().update_stock_quantity(product_name="fantasma", delta=-1)

    assert resultado["status"] == "error"
    assert "Nenhum item de estoque encontrado" in resultado["message"]


def test_update_quantidade_negativa_preserva_a_mensagem_de_dominio(monkeypatch):
    _fingir(monkeypatch, "atualizar_quantidade", erro=QuantidadeNegativa())

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().update_stock_quantity(stock_product_id=5, delta=-99)

    assert resultado["status"] == "error"
    assert "negativa" in resultado["message"]


def _fake_descarte(stock_product_id=9, product_name="Leite", quantidade_perdida=3):
    return {
        "stock_product_id": stock_product_id,
        "product_name": product_name,
        "quantidade_perdida": quantidade_perdida,
    }


def test_discard_repassa_motivo_e_contexto(monkeypatch):
    captura: dict = {}
    _fingir(monkeypatch, "descartar", retorno=_fake_descarte(), captura=captura)
    monkeypatch.setattr(
        "frigus_ai.graph.tools.estoque.repo.ranking.registrar_descarte", lambda *a, **kw: None
    )

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().discard_product(product_name="Leite", reason="Estragado")

    stock_id, user_id, item_id, nome, motivo = captura["args"]
    assert (stock_id, user_id, nome, motivo) == (42, 7, "Leite", "Estragado")
    assert item_id is None
    assert resultado["stock_product_id"] == 9


def test_discard_erro_vira_response_error(monkeypatch):
    _fingir(monkeypatch, "descartar", erro=ItemDeEstoqueNaoEncontrado())

    with session_context(**CONTEXTO):
        assert EstoqueRepo().discard_product(stock_product_id=1)["status"] == "error"


def test_discard_alimenta_o_ranking_de_desperdicio(monkeypatch):
    _fingir(monkeypatch, "descartar", retorno=_fake_descarte(quantidade_perdida=3))
    capturado: dict = {}

    def _fake_registrar(stock_id, product_name, quantidade):
        capturado["args"] = (stock_id, product_name, quantidade)

    monkeypatch.setattr(
        "frigus_ai.graph.tools.estoque.repo.ranking.registrar_descarte", _fake_registrar
    )

    with session_context(**CONTEXTO):
        EstoqueRepo().discard_product(stock_product_id=9, reason="Vencido")

    assert capturado["args"] == (42, "Leite", 3)


def test_discard_sem_quantidade_nao_alimenta_o_ranking(monkeypatch):
    _fingir(monkeypatch, "descartar", retorno=_fake_descarte(quantidade_perdida=0))

    def _nao_deveria(*args, **kwargs):
        raise AssertionError("não deveria registrar ranking pra item já zerado")

    monkeypatch.setattr(
        "frigus_ai.graph.tools.estoque.repo.ranking.registrar_descarte", _nao_deveria
    )

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().discard_product(stock_product_id=9)

    assert resultado["status"] == "ok"


def test_discard_falha_no_ranking_nao_derruba_o_descarte(monkeypatch):
    """Redis é estatística — o descarte no Postgres já deu certo, não pode virar erro."""

    _fingir(monkeypatch, "descartar", retorno=_fake_descarte())

    def _falha(*args, **kwargs):
        raise RuntimeError("redis fora do ar")

    monkeypatch.setattr("frigus_ai.graph.tools.estoque.repo.ranking.registrar_descarte", _falha)

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().discard_product(stock_product_id=9)

    assert resultado["status"] == "ok"


def test_as_tools_expoe_as_cinco_tools():
    nomes = {t.name for t in EstoqueRepo().as_tools()}

    assert nomes == {
        "add_stock_product", "add_stock_products", "query_stock", "update_stock_quantity", "discard_product"
    }


def test_add_stock_products_grava_o_lote_numa_chamada_e_devolve_cada_item(monkeypatch):
    captura: dict = {}
    _fingir(monkeypatch, "adicionar_produtos", retorno=[(10, 2), (11, 1)], captura=captura)
    validade = (date.today() + timedelta(days=30)).isoformat()

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().add_stock_products([
            {"product_name": "Leite", "category": "Laticínio", "storage_place": "Geladeira",
             "quantity": 2, "expire_date": validade},
            {"product_name": "Arroz", "category": "Grão", "storage_place": "Despensa",
             "quantity": 1, "expire_date": validade},
        ])

    stock_id, dados = captura["args"]
    assert stock_id == 42
    assert [d["product_name"] for d in dados] == ["Leite", "Arroz"]
    assert resultado["status"] == "ok"
    assert resultado["total_adicionados"] == 2
    assert [i["stock_product_id"] for i in resultado["itens"]] == [10, 11]


def test_add_stock_products_com_item_invalido_nao_chega_no_banco(monkeypatch):
    chamado = []
    monkeypatch.setattr(estoque_repository, "adicionar_produtos", lambda *a, **kw: chamado.append(1))

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().add_stock_products([
            {"product_name": "Leite", "category": "Laticínio", "storage_place": "Geladeira",
             "quantity": 2, "expire_date": "ontem"},
        ])

    assert resultado["status"] == "error"
    assert chamado == []


def test_update_com_nome_resolvido_manda_o_id_e_nao_o_nome(monkeypatch):
    captura: dict = {}
    monkeypatch.setattr(repo_mod, "resolver_item", lambda stock_id, nome: 77)
    _fingir(monkeypatch, "atualizar_quantidade", retorno=(77, 3), captura=captura)

    with session_context(**CONTEXTO):
        resultado = EstoqueRepo().update_stock_quantity(product_name="leite", delta=-1)

    assert captura["args"] == (42, 7, 77, None, -1, None)
    assert resultado["status"] == "ok"


def test_nome_ambiguo_vira_pergunta_e_nao_toca_no_banco(monkeypatch):
    chamado = []

    def _ambiguo(stock_id, nome):
        raise NomeAmbiguo("Não sei qual item é 'leite'. Opções: A; B.")

    monkeypatch.setattr(repo_mod, "resolver_item", _ambiguo)
    monkeypatch.setattr(estoque_repository, "atualizar_quantidade", lambda *a, **kw: chamado.append(1))
    monkeypatch.setattr(estoque_repository, "descartar", lambda *a, **kw: chamado.append(1))

    with session_context(**CONTEXTO):
        atualizar = EstoqueRepo().update_stock_quantity(product_name="leite", delta=-1)
        descartar = EstoqueRepo().discard_product(product_name="leite")

    assert atualizar["status"] == descartar["status"] == "error"
    assert "Não sei qual item" in atualizar["message"]
    assert chamado == []


def test_com_id_o_resolvedor_nem_roda(monkeypatch):
    def _nao_devia(stock_id, nome):
        raise AssertionError("resolvedor chamado com id direto")

    monkeypatch.setattr(repo_mod, "resolver_item", _nao_devia)
    _fingir(monkeypatch, "descartar", retorno={"stock_product_id": 5, "product_name": "Leite", "quantidade_perdida": 0})

    with session_context(**CONTEXTO):
        assert EstoqueRepo().discard_product(stock_product_id=5)["status"] == "ok"
