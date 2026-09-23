"""
Contrato HTTP das rotas de estoque. Mesmo desenho de `test_chats.py`: `estoque_repository`
e `user_service` viram stubs, então o que se testa é status/body/exception mapping — não
o domínio (SQLAlchemy), que já tem teste próprio em `tests/repositories/`.
"""

import pytest
from fastapi.testclient import TestClient

from frigus_ai.api.app import app
from frigus_ai.api.routes import stock as rotas
from frigus_ai.exceptions import ItemDeEstoqueNaoEncontrado
from frigus_ai.services.user_service import user_service


@pytest.fixture
def cliente(monkeypatch):
    async def _resolver_stock_id(user_id):
        return 1

    async def _obter_ou_criar_padrao():
        return 1

    monkeypatch.setattr(user_service, "resolver_stock_id", _resolver_stock_id)
    monkeypatch.setattr(user_service, "obter_ou_criar_padrao", _obter_ou_criar_padrao)

    return TestClient(app, raise_server_exceptions=False)


def test_create_item_calcula_status_e_devolve_201(cliente, monkeypatch):
    def _adicionar_produto(stock_id, dados):
        assert stock_id == 1
        assert dados["product_status"] == "Fresco"
        return 42, dados["quantity"]

    monkeypatch.setattr(rotas.estoque_repository, "adicionar_produto", _adicionar_produto)

    r = cliente.post(
        "/stock/items",
        json={
            "product_name": "Leite integral",
            "category": "Laticínio",
            "storage_place": "Geladeira",
            "quantity": 2,
            "expire_date": "2999-01-01",
        },
    )

    assert r.status_code == 201
    body = r.json()
    assert body == {"stock_product_id": 42, "quantity": 2, "product_status": "Fresco"}


def test_update_item_sem_delta_nem_novo_valor_e_422(cliente):
    r = cliente.put("/stock/items/1", json={})
    assert r.status_code == 422


def test_item_nao_encontrado_vira_404(cliente, monkeypatch):
    def _atualizar_quantidade(*args, **kwargs):
        raise ItemDeEstoqueNaoEncontrado

    monkeypatch.setattr(rotas.estoque_repository, "atualizar_quantidade", _atualizar_quantidade)

    r = cliente.put("/stock/items/999", json={"delta": 1})

    assert r.status_code == 404
    assert r.json()["code"] == "estoque_item_nao_encontrado"


def test_estoque_nao_definido_vira_409(monkeypatch):
    async def _sem_estoque(user_id):
        return None

    async def _obter_ou_criar_padrao():
        return 1

    monkeypatch.setattr(user_service, "resolver_stock_id", _sem_estoque)
    monkeypatch.setattr(user_service, "obter_ou_criar_padrao", _obter_ou_criar_padrao)
    cliente = TestClient(app, raise_server_exceptions=False)

    r = cliente.get("/stock/items")

    assert r.status_code == 409
    assert r.json()["code"] == "estoque_nao_definido"


def test_analisar_foto_devolve_a_resposta_do_grafo(cliente, monkeypatch):
    chamado_com = {}

    async def _analisar_foto(user_id, stock_id, imagem):
        chamado_com["args"] = (user_id, stock_id, imagem)
        return "Você tem leite e ovos na geladeira."

    monkeypatch.setattr(rotas.chat_service, "analisar_foto", _analisar_foto)

    r = cliente.post("/stock/foto", files={"foto": ("geladeira.jpg", b"conteudo-fake", "image/jpeg")})

    assert r.status_code == 200
    assert r.json() == {"resposta": "Você tem leite e ovos na geladeira."}
    assert chamado_com["args"] == (1, 1, b"conteudo-fake")


def test_analisar_foto_maior_que_o_limite_vira_413(cliente):
    foto_grande = b"x" * (rotas._MAX_FOTO_BYTES + 1)

    r = cliente.post("/stock/foto", files={"foto": ("geladeira.jpg", foto_grande, "image/jpeg")})

    assert r.status_code == 413
