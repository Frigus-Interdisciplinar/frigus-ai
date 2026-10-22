"""
Nome em linguagem natural -> item do estoque: só resolve sozinho quando é inequívoco; no resto o JeV
escolhe entre os itens do usuário, e sem convicção (ou sem JeV, com vários parecidos) a tool pergunta.
O estoque e o JeV são stubs: o que se checa é a decisão, não o SQL nem o gateway.
"""

import pytest

from frigus_ai.graph.tools.estoque import resolver
from frigus_ai.graph.tools.estoque.resolver import NomeAmbiguo, resolver_item
from frigus_ai.infra.llm.jev import Decisoes
from frigus_ai.infra.llm.jev.schemas import Escolha
from frigus_ai.repositories import estoque_repository


def _item(item_id, nome, validade="2026-12-01"):
    return {"stock_product_id": item_id, "product_name": nome, "expire_date": validade}


@pytest.fixture
def estoque(monkeypatch):
    def definir(itens):
        monkeypatch.setattr(estoque_repository, "consultar_estoque", lambda stock_id, filtros: itens)

    return definir


@pytest.fixture
def jev_escolhe(monkeypatch):
    """Faz o JeV responder `escolha` com `chance`; guarda a pergunta em `perguntas`."""

    perguntas = []

    def definir(escolha, chance=0.95):
        async def decidir(uso, entrada, perguntas_enviadas):
            perguntas.append((uso, entrada, perguntas_enviadas))
            probabilidades = [{"value": escolha, "probability": chance}] if chance is not None else []
            return Decisoes({"item": Escolha(type="choice", name="item", choice=escolha, probabilities=probabilidades)})

        monkeypatch.setattr(resolver.jev, "disponivel", lambda: True)
        monkeypatch.setattr(resolver.jev, "decidir", decidir)

    definir.perguntas = perguntas
    return definir


def test_nome_exato_resolve_sem_acento_e_sem_caixa_e_sem_chamar_o_jev(estoque, monkeypatch):
    estoque([_item(1, "Feijão"), _item(2, "Feijão preto")])
    monkeypatch.setattr(resolver.jev, "decidir", lambda *a, **kw: pytest.fail("não devia chamar o JeV"))

    assert resolver_item(42, "feijao") == 1


def test_um_unico_parecido_resolve_sem_chamar_o_jev(estoque, monkeypatch):
    estoque([_item(1, "Leite integral"), _item(2, "Arroz")])
    monkeypatch.setattr(resolver.jev, "decidir", lambda *a, **kw: pytest.fail("não devia chamar o JeV"))

    assert resolver_item(42, "leite") == 1


def test_varias_validades_do_mesmo_produto_pegam_a_que_vence_antes(estoque, monkeypatch):
    estoque([_item(7, "Leite integral", "2026-11-01"), _item(8, "Leite integral", "2026-12-01")])
    monkeypatch.setattr(resolver.jev, "decidir", lambda *a, **kw: pytest.fail("não devia chamar o JeV"))

    assert resolver_item(42, "leite") == 7


def test_produtos_diferentes_parecidos_vao_pro_jev_com_opcoes_dinamicas(estoque, jev_escolhe):
    estoque([_item(1, "Leite integral"), _item(2, "Leite de coco"), _item(3, "Arroz")])
    jev_escolhe("2")

    assert resolver_item(42, "leite de coco") == 2  # exato resolve; este caso é o parecido abaixo
    assert resolver_item(42, "leite") == 2

    uso, _, [pergunta] = jev_escolhe.perguntas[0]
    assert uso == "estoque_nome"
    assert pergunta.dinamica is True
    assert [c.value for c in pergunta.choices] == ["1", "2", "nenhum"]  # só os parecidos, mais o "nenhum"
    assert "dinamica" not in pergunta.model_dump(mode="json")  # a marca não vai pro gateway


def test_sem_nenhum_parecido_o_jev_acha_o_plural_no_estoque_inteiro(estoque, jev_escolhe):
    estoque([_item(1, "Ovo"), _item(2, "Arroz")])
    jev_escolhe("1")

    assert resolver_item(42, "ovos") == 1
    assert [c.value for c in jev_escolhe.perguntas[0][2][0].choices] == ["1", "2", "nenhum"]


def test_sem_convicao_pergunta_ao_usuario_com_as_opcoes(estoque, jev_escolhe):
    estoque([_item(1, "Leite integral"), _item(2, "Leite de coco")])
    jev_escolhe("1", chance=0.55)

    with pytest.raises(NomeAmbiguo, match="Leite integral.*Leite de coco"):
        resolver_item(42, "leite")


def test_sem_probabilidades_do_gateway_vale_a_escolha(estoque, jev_escolhe):
    estoque([_item(1, "Leite integral"), _item(2, "Leite de coco")])
    jev_escolhe("2", chance=None)

    assert resolver_item(42, "leite") == 2


def test_nenhum_com_varios_parecidos_pergunta_e_sem_parecidos_deixa_o_repository_falhar(estoque, jev_escolhe):
    estoque([_item(1, "Leite integral"), _item(2, "Leite de coco")])
    jev_escolhe("nenhum")

    with pytest.raises(NomeAmbiguo):
        resolver_item(42, "leite")
    assert resolver_item(42, "picanha") is None


def test_sem_jev_varios_parecidos_perguntam_em_vez_de_adivinhar(estoque, monkeypatch):
    estoque([_item(1, "Leite integral"), _item(2, "Leite de coco")])
    monkeypatch.setattr(resolver.jev, "disponivel", lambda: False)

    with pytest.raises(NomeAmbiguo):
        resolver_item(42, "leite")
    assert resolver_item(42, "picanha") is None


def test_jev_falhando_cai_no_mesmo_comportamento_seguro(estoque, monkeypatch):
    estoque([_item(1, "Leite integral"), _item(2, "Leite de coco"), _item(3, "Ovo")])

    async def quebra(*a, **kw):
        raise RuntimeError("gateway fora")

    monkeypatch.setattr(resolver.jev, "disponivel", lambda: True)
    monkeypatch.setattr(resolver.jev, "decidir", quebra)

    with pytest.raises(NomeAmbiguo):
        resolver_item(42, "leite")
    assert resolver_item(42, "ovos") is None


def test_estoque_vazio_nao_chama_o_jev(estoque, monkeypatch):
    estoque([])
    monkeypatch.setattr(resolver.jev, "decidir", lambda *a, **kw: pytest.fail("não devia chamar o JeV"))

    assert resolver_item(42, "leite") is None
