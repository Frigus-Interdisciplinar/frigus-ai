"""
Uma execução ponta a ponta do grafo com os agentes/LLMs stubados.

Cobre o que os contratos tipados (`EntradaGrafo`/`SaidaGrafo` + os `*Update`) prometem e que
nenhum teste de nó isolado pega: que as chaves dos TypedDicts batem com as do `Estado` (um typo
viraria update silenciosamente descartado pelo LangGraph), que `agentes_chamados` acumula pelo
reducer sem ser semeado na entrada, que o laço do Juiz volta pro especialista de origem, e que a
saída expõe só `messages`.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.graph import builder
from frigus_ai.graph.state import EntradaGrafo


class _FakeAgente:
    """Substitui um `create_agent` compilado: devolve sempre o mesmo texto."""

    def __init__(self, texto):
        self._texto = texto
        self.chamadas = 0

    async def ainvoke(self, entrada):
        self.chamadas += 1
        return {"messages": [*entrada["messages"], AIMessage(content=self._texto)]}


class _FakeLLM:
    def __init__(self, respostas):
        self._respostas = list(respostas)

    async def ainvoke(self, _entrada):
        texto = self._respostas.pop(0) if len(self._respostas) > 1 else self._respostas[0]
        return AIMessage(content=texto)


@pytest.fixture
def grafo(monkeypatch):
    """Stuba tudo que faz I/O: os agentes dos nós e os LLMs de guardrail/juiz."""

    from frigus_ai.graph.guardrail import entrada as entrada_mod
    from frigus_ai.graph.guardrail import saida as saida_mod
    from frigus_ai.graph.nodes import estoque as estoque_mod
    from frigus_ai.graph.nodes import juiz as no_juiz_mod
    from frigus_ai.graph.nodes import orquestrador as orq_mod
    from frigus_ai.graph.nodes import router as router_mod

    agentes = {
        "router":       _FakeAgente("ROUTE=estoque\nPERGUNTA_ORIGINAL=o que tem na geladeira"),
        "estoque":      _FakeAgente('{"itens": ["leite"]}'),
        "orquestrador": _FakeAgente("Você tem leite na geladeira."),
    }
    monkeypatch.setattr(router_mod,   "router_app",       agentes["router"])
    monkeypatch.setattr(estoque_mod,  "estoque_app",      agentes["estoque"])
    monkeypatch.setattr(orq_mod,      "orquestrador_app", agentes["orquestrador"])

    # Guardrail de entrada aprova, guardrail de saída devolve o texto revisado.
    monkeypatch.setattr(entrada_mod, "llm_guardrail", _FakeLLM(["CATEGORIA: APROVADO"]))
    monkeypatch.setattr(
        saida_mod, "llm_rapido", _FakeLLM(["RESPOSTA: Você tem leite na geladeira."])
    )

    def compilar(vereditos):
        monkeypatch.setattr(no_juiz_mod, "llm_juiz", _FakeLLM(vereditos))
        return builder._construir_grafo().compile()

    return compilar, agentes


async def test_fluxo_feliz_ate_o_guardrail_de_saida(grafo):
    compilar, agentes = grafo
    app = compilar(["VEREDITO: APROVADO\nJUSTIFICATIVA: ok"])

    saida = await app.ainvoke(
        EntradaGrafo(messages=[HumanMessage(content="o que tem na geladeira?")])
    )

    # SaidaGrafo não expõe rota/mapa_pii — só o histórico de mensagens.
    assert set(saida) == {"messages"}
    assert saida["messages"][-1].content == "Você tem leite na geladeira."
    assert agentes["estoque"].chamadas == 1


async def test_juiz_reprovado_volta_pro_especialista_de_origem(grafo):
    compilar, agentes = grafo
    app = compilar([
        "VEREDITO: REPROVADO\nJUSTIFICATIVA: faltou citar a validade",
        "VEREDITO: APROVADO\nJUSTIFICATIVA: ok",
    ])

    await app.ainvoke(EntradaGrafo(messages=[HumanMessage(content="o que tem na geladeira?")]))

    # Reprovado uma vez -> estoque roda de novo com o feedback, depois o Juiz aprova.
    assert agentes["estoque"].chamadas == 2


async def test_agentes_chamados_acumula_sem_ser_semeado_na_entrada(grafo):
    """`agentes_chamados` não está em EntradaGrafo: quem cria a lista é o reducer operator.add."""

    compilar, _ = grafo
    app = compilar(["VEREDITO: APROVADO\nJUSTIFICATIVA: ok"])

    estado = await app.ainvoke(
        EntradaGrafo(messages=[HumanMessage(content="o que tem na geladeira?")]),
        config={"configurable": {"thread_id": "t1"}},
    )
    del estado

    # O estado interno completo não sai pelo SaidaGrafo; lemos pelo próprio grafo.
    interno = await app.ainvoke(
        EntradaGrafo(messages=[HumanMessage(content="e agora?")]),
        config={"configurable": {"thread_id": "t2"}},
        output_keys=["agentes_chamados"],
    )

    assert interno["agentes_chamados"] == [
        "guardrail_entrada_node",
        "roteador_node",
        "estoque_node",
        "orquestrador_node",
        "juiz_node",
        "guardrail_saida_node",
    ]


async def test_turno_com_imagem_pula_o_roteador_e_vai_pra_visao(grafo, monkeypatch):
    """`decidir_apos_guardrail_entrada` desvia direto pra Visão quando há `imagem_b64` —
    o roteador (LLM de texto) nunca roda nesse turno."""

    from frigus_ai.graph import state as state_mod
    from frigus_ai.graph.nodes import visao as visao_mod

    inventario = state_mod.InventarioGeladeira(
        items=[
            state_mod.ItemIdentificado(
                product_name="Leite integral",
                quantity=1,
                unit="litro",
                category="Laticínio",
                storage_place="Geladeira",
            )
        ],
        confidence=0.9,
    )

    class _FakeLLMVisao:
        async def ainvoke(self, _mensagens):
            return inventario

    monkeypatch.setattr(visao_mod, "llm_visao", _FakeLLMVisao())

    compilar, agentes = grafo
    app = compilar(["VEREDITO: APROVADO\nJUSTIFICATIVA: ok"])

    await app.ainvoke(
        EntradaGrafo(
            messages=[HumanMessage(content="analise esta foto")],
            imagem_b64="ZmFrZQ==",
        )
    )

    assert agentes["router"].chamadas == 0
    assert agentes["orquestrador"].chamadas == 1
