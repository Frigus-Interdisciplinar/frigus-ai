"""Itens da foto que o JeV não consegue ver viram pergunta pro usuário; sem gateway, a lista passa direto."""

import json

import pytest

from frigus_ai.domain.errors import FalhaNoAgente
from frigus_ai.graph.nodes import visao as visao_mod
from frigus_ai.graph.state import ContextoPrompt, InventarioGeladeira, ItemIdentificado
from frigus_ai.infra.llm.jev import client
from frigus_ai.infra.llm.jev.schemas import Predicado


def _item(nome: str) -> ItemIdentificado:
    return ItemIdentificado(product_name=nome, quantity=1, unit="un", category="Bebida", storage_place="Geladeira")


class _LLMVisao:
    async def ainvoke(self, _msgs):
        return InventarioGeladeira(items=[_item("Leite"), _item("Iogurte")], confidence=0.9)


def _predicado(nome: str, probabilidade: float) -> Predicado:
    return Predicado(type="predicate", name=nome, probability=probabilidade)


class _Runtime:
    def __init__(self, context):
        self.context = context


def _runtime(imagem_b64: str | None = "ZmFrZQ=="):
    return _Runtime(ContextoPrompt(imagem_b64=imagem_b64))


@pytest.fixture
def visao(monkeypatch):
    monkeypatch.setattr(visao_mod, "llm_visao", _LLMVisao())
    monkeypatch.setattr(visao_mod.jev, "disponivel", lambda: True)


async def test_item_que_nao_aparece_na_foto_vira_esclarecer(visao, monkeypatch):
    chamadas = []

    async def decidir(uso, entrada, perguntas, imagem_b64=None):
        chamadas.append((uso, [p.name for p in perguntas], imagem_b64))
        return client.Decisoes({"item_0": _predicado("item_0", 0.95), "item_1": _predicado("item_1", 0.2)})

    monkeypatch.setattr(visao_mod.jev, "decidir", decidir)

    update = await visao_mod.no_visao({"tem_imagem": True}, _runtime())

    [resultado] = update["dados_especialistas"]
    assert chamadas == [("visao", ["item_0", "item_1"], "ZmFrZQ==")]
    assert "Iogurte" in json.loads(resultado["dados"])["esclarecer"]
    assert "Leite" not in json.loads(resultado["dados"])["esclarecer"]


async def test_todos_na_foto_nao_pedem_confirmacao(visao, monkeypatch):
    async def decidir(*_args, **_kw):
        return client.Decisoes({"item_0": _predicado("item_0", 0.9), "item_1": _predicado("item_1", 0.8)})

    monkeypatch.setattr(visao_mod.jev, "decidir", decidir)

    [resultado] = (await visao_mod.no_visao({"tem_imagem": True}, _runtime()))["dados_especialistas"]

    assert "esclarecer" not in json.loads(resultado["dados"])


async def test_gateway_falhando_entrega_a_lista_sem_marcar_ninguem(visao, monkeypatch):
    async def decidir(*_args, **_kw):
        raise RuntimeError("fora do ar")

    monkeypatch.setattr(visao_mod.jev, "decidir", decidir)

    [resultado] = (await visao_mod.no_visao({"tem_imagem": True}, _runtime()))["dados_especialistas"]

    dados = json.loads(resultado["dados"])
    assert [i["product_name"] for i in dados["items"]] == ["Leite", "Iogurte"]
    assert "esclarecer" not in dados


async def test_turno_de_foto_sem_imagem_no_contexto_falha_claro(visao):
    with pytest.raises(FalhaNoAgente, match="sem imagem"):
        await visao_mod.no_visao({"tem_imagem": True}, _runtime(None))
