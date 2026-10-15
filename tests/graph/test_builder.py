"""
Uma execução ponta a ponta do grafo com os agentes/LLMs stubados.

Cobre o que os contratos tipados (`EntradaGrafo`/`SaidaGrafo` + os `*Update`) prometem e que
nenhum teste de nó isolado pega: que as chaves dos TypedDicts batem com as do `Estado` (um typo
viraria update silenciosamente descartado pelo LangGraph), que `dados_especialistas` acumula pelo
reducer, que especialistas escolhidos juntos rodam em paralelo
e o orquestrador espera todos, que o laço do Juiz volta só pro orquestrador, e que a saída expõe
só `messages`.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.domain.errors import AssessorIndisponivel
from frigus_ai.graph import builder
from frigus_ai.graph.guardrail.schemas import (
    Categoria,
    Classificacao,
    RevisaoCompliance,
)
from frigus_ai.graph.names import ESTOQUE
from frigus_ai.graph.nodes.especialista import especialista_com_agente
from frigus_ai.graph.nodes.juiz import VereditoJuiz
from frigus_ai.graph.state import EntradaGrafo, Roteamento


class _FakeAgente:
    """Substitui um `create_agent` compilado: devolve sempre o mesmo texto."""

    def __init__(self, texto):
        self._texto = texto
        self.chamadas = 0
        self.entradas = []

    async def ainvoke(self, entrada, **_kwargs):
        self.chamadas += 1
        self.entradas.append(entrada["messages"])
        return {"messages": [*entrada["messages"], AIMessage(content=self._texto)]}


class _FakeRoteador:
    """Substitui o `router_app` (create_agent com `response_format`)."""

    def __init__(self, roteamento):
        self._roteamento = roteamento
        self.chamadas = 0

    async def ainvoke(self, entrada, **_kwargs):
        self.chamadas += 1
        return {"messages": entrada["messages"], "structured_response": self._roteamento}


class _FakeLLM:
    """Devolve os objetos estruturados em sequência; o último se repete."""

    def __init__(self, respostas):
        self._respostas = list(respostas)

    async def ainvoke(self, _entrada):
        return self._respostas.pop(0) if len(self._respostas) > 1 else self._respostas[0]


class _FakeClassificador:
    async def ainvoke(self, _entrada):
        return Classificacao(categoria=Categoria.APROVADO, justificativa="ok")


@pytest.fixture
def grafo(monkeypatch):
    """Stuba tudo que faz I/O: os agentes dos nós e os LLMs de guardrail/juiz."""

    from frigus_ai.graph.guardrail import entrada as entrada_mod
    from frigus_ai.graph.guardrail import saida as saida_mod
    from frigus_ai.graph.nodes import juiz as no_juiz_mod
    from frigus_ai.graph.nodes import orquestrador as orq_mod
    from frigus_ai.graph.nodes import router as router_mod

    agentes = {
        "router":       _FakeRoteador(Roteamento(especialistas=["estoque"])),
        "estoque":      _FakeAgente('{"itens": ["leite"]}'),
        "orquestrador": _FakeAgente("Você tem leite na geladeira."),
    }
    monkeypatch.setattr(router_mod,   "router_app",       agentes["router"])
    # A fábrica captura o agente no import, então o que se troca é o nó que o builder usa.
    monkeypatch.setattr(builder, "no_estoque", especialista_com_agente(ESTOQUE, agentes["estoque"]))
    monkeypatch.setattr(orq_mod,      "orquestrador_app", agentes["orquestrador"])

    # Guardrail de entrada aprova, guardrail de saída devolve o texto revisado.
    monkeypatch.setattr(entrada_mod, "llm_classificador", _FakeClassificador())
    monkeypatch.setattr(
        saida_mod,
        "llm_revisor",
        _FakeLLM([RevisaoCompliance(revisada="Você tem leite na geladeira.", modificada=False)]),
    )

    def compilar(vereditos):
        monkeypatch.setattr(no_juiz_mod, "llm_avaliador", _FakeLLM(vereditos))
        return builder._construir_grafo().compile()

    return compilar, agentes


async def _rodar(app, texto: str, thread_id: str = "t") -> tuple[list[str], list]:
    """Os nós que rodaram, na ordem, e o histórico final do turno."""

    caminho, mensagens = [], []
    async for modo, dados in app.astream(
        EntradaGrafo(messages=[HumanMessage(content=texto)]),
        config={"configurable": {"thread_id": thread_id}},
        stream_mode=["updates", "values"],
    ):
        if modo == "updates":
            caminho.extend(dados)
        else:
            mensagens = dados["messages"]

    return caminho, mensagens


async def test_fluxo_feliz_ate_o_guardrail_de_saida(grafo):
    compilar, agentes = grafo
    app = compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])

    saida = await app.ainvoke(
        EntradaGrafo(messages=[HumanMessage(content="o que tem na geladeira?")])
    )

    # SaidaGrafo não expõe rota/mapa_pii — só o histórico e se o guardrail bloqueou o turno.
    assert set(saida) == {"messages", "mensagem_bloqueada"}
    assert saida["mensagem_bloqueada"] is None
    assert saida["messages"][-1].content == "Você tem leite na geladeira."
    assert agentes["estoque"].chamadas == 1
    # Só o guardrail de saída publica: especialista e orquestrador não deixam resposta intermediária
    # no histórico que volta pro LLM no turno seguinte.
    assert [type(m) for m in saida["messages"]] == [HumanMessage, AIMessage]


async def test_juiz_reprovado_reescreve_no_orquestrador_sem_repetir_o_especialista(grafo):
    """Repetir o especialista regravaria estoque/lista de compras; a reprovação costuma ser da
    redação, que o orquestrador refaz com o feedback."""

    compilar, agentes = grafo
    app = compilar([
        VereditoJuiz(veredito="REPROVADO", justificativa="faltou citar a validade"),
        VereditoJuiz(veredito="APROVADO", justificativa="ok"),
    ])

    await app.ainvoke(EntradaGrafo(messages=[HumanMessage(content="o que tem na geladeira?")]))

    assert agentes["estoque"].chamadas == 1
    assert agentes["orquestrador"].chamadas == 2
    primeira, segunda = (entrada[0].content for entrada in agentes["orquestrador"].entradas)
    assert "[REVISÃO SOLICITADA PELO JUIZ]" not in primeira
    assert "[REVISÃO SOLICITADA PELO JUIZ] faltou citar a validade" in segunda


async def test_caminho_do_turno_de_estoque(grafo):
    compilar, _ = grafo
    app = compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])

    caminho, _ = await _rodar(app, "o que tem na geladeira?")

    assert caminho == [
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
    app = compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])

    await app.ainvoke(
        EntradaGrafo(
            messages=[HumanMessage(content="analise esta foto")],
            imagem_b64="ZmFrZQ==",
        )
    )

    assert agentes["router"].chamadas == 0
    assert agentes["orquestrador"].chamadas == 1


async def test_juiz_reprovado_em_turno_de_foto_reescreve_no_orquestrador(grafo, monkeypatch):
    """A foto não precisa ser reanalisada: o retry leva o feedback pro orquestrador."""

    from frigus_ai.graph import state as state_mod
    from frigus_ai.graph.nodes import visao as visao_mod

    inventario = state_mod.InventarioGeladeira(items=[], confidence=0.5)
    prompts = []

    class _FakeLLMVisao:
        async def ainvoke(self, mensagens):
            prompts.append(mensagens[0].content[0]["text"])
            return inventario

    monkeypatch.setattr(visao_mod, "llm_visao", _FakeLLMVisao())

    compilar, agentes = grafo
    app = compilar([
        VereditoJuiz(veredito="REPROVADO", justificativa="não listou os itens"),
        VereditoJuiz(veredito="APROVADO", justificativa="ok"),
    ])

    await app.ainvoke(
        EntradaGrafo(messages=[HumanMessage(content="analise esta foto")], imagem_b64="ZmFrZQ==")
    )

    assert len(prompts) == 1
    assert agentes["orquestrador"].chamadas == 2
    assert "[REVISÃO SOLICITADA PELO JUIZ] não listou os itens" in agentes["orquestrador"].entradas[1][0].content


async def test_plano_de_economia_vai_pro_assessor_e_passa_pelo_juiz(grafo, monkeypatch):
    from frigus_ai.graph.nodes import assessor as assessor_mod
    from frigus_ai.graph.nodes import router as router_mod

    perguntas = []

    async def _perguntar(pergunta, session_id):
        perguntas.append((pergunta, session_id))
        return "Seu saldo é R$ 1.200,00."

    monkeypatch.setattr(router_mod, "router_app", _FakeRoteador(Roteamento(especialistas=["assessor"])))
    monkeypatch.setattr(assessor_mod.assessor, "perguntar", _perguntar)

    compilar, _ = grafo
    app = compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])

    caminho, mensagens = await _rodar(app, "como economizo no mercado?", thread_id="chat-9")

    assert perguntas[0][1] == "chat-9"  # session_id vem do thread_id
    assert caminho == [
        "guardrail_entrada_node", "roteador_node", "a2a_assessor_node",
        "orquestrador_node", "juiz_node", "guardrail_saida_node",
    ]
    assert mensagens[-1].content == "Seu saldo é R$ 1.200,00."


async def test_assessor_fora_do_ar_responde_limpo_sem_passar_pelo_juiz(grafo, monkeypatch):
    from frigus_ai.graph.nodes import assessor as assessor_mod
    from frigus_ai.graph.nodes import router as router_mod

    async def _fora_do_ar(pergunta, session_id):
        raise AssessorIndisponivel("connection refused")

    monkeypatch.setattr(router_mod, "router_app", _FakeRoteador(Roteamento(especialistas=["assessor"])))
    monkeypatch.setattr(assessor_mod.assessor, "perguntar", _fora_do_ar)

    compilar, _ = grafo
    app = compilar([VereditoJuiz(veredito="REPROVADO", justificativa="não deveria ser chamado")])

    caminho, mensagens = await _rodar(app, "como economizo no mercado?", thread_id="chat-9")

    assert "juiz_node" not in caminho
    assert mensagens[-1].content == assessor_mod.INDISPONIVEL


async def test_stream_do_runner_transmite_o_caminho_do_assessor(grafo, monkeypatch):
    """O `executar_stream` real sobre o grafo compilado: os eventos que o painel do front
    consome saem com o nome do nó novo e com a rota escolhida pelo roteador."""

    from frigus_ai.graph.nodes import assessor as assessor_mod
    from frigus_ai.graph.nodes import router as router_mod
    from frigus_ai.repositories import chat_embeddings_repository
    from frigus_ai.services import runner

    async def _perguntar(pergunta, session_id):
        return "Reserve R$ 600,00 por mês."

    async def _sem_conversas(user_id, pergunta, session_id_atual):
        return []

    class _Fluxo:
        def __init__(self, compilado):
            self._compilado = compilado

        async def get(self):
            return self._compilado

    monkeypatch.setattr(router_mod, "router_app", _FakeRoteador(Roteamento(especialistas=["assessor"])))
    monkeypatch.setattr(assessor_mod.assessor, "perguntar", _perguntar)
    monkeypatch.setattr(chat_embeddings_repository, "buscar_resumos_relevantes", _sem_conversas)

    compilar, _ = grafo
    monkeypatch.setattr(runner, "fluxo_agentes", _Fluxo(compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])))

    eventos = [e async for e in runner.executar_stream("como economizo?", "chat-9", 7, None)]

    iniciados = [e.node for e in eventos if e.type == "node_started"]
    assert iniciados == [
        "guardrail_entrada_node", "roteador_node", "a2a_assessor_node",
        "orquestrador_node", "juiz_node", "guardrail_saida_node",
    ]
    assert [e.route for e in eventos if e.type == "route_selected"] == ["assessor"]
    assert [e.content for e in eventos if e.type == "answer_ready"] == ["Reserve R$ 600,00 por mês."]
    assert eventos[-1].type == "run_finished"


async def test_stream_do_runner_transmite_a_rota_da_visao(grafo, monkeypatch):
    from frigus_ai.graph import state as state_mod
    from frigus_ai.graph.nodes import visao as visao_mod
    from frigus_ai.services import runner

    class _FakeLLMVisao:
        async def ainvoke(self, _mensagens):
            return state_mod.InventarioGeladeira(items=[], confidence=0.5)

    class _Fluxo:
        def __init__(self, compilado):
            self._compilado = compilado

        async def get(self):
            return self._compilado

    monkeypatch.setattr(visao_mod, "llm_visao", _FakeLLMVisao())
    compilar, _ = grafo
    monkeypatch.setattr(runner, "fluxo_agentes", _Fluxo(compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])))

    eventos = [
        e async for e in runner.executar_stream("foto", "visao-7-x", 7, None, imagem_b64="ZmFrZQ==")
    ]

    assert [e.route for e in eventos if e.type == "route_selected"] == ["visao"]
    assert "visao_node" in [e.node for e in eventos if e.type == "node_started"]


def _com_receitas(monkeypatch, texto="Omelete de queijo."):
    from frigus_ai.graph.names import RECEITAS

    receitas = _FakeAgente(texto)
    monkeypatch.setattr(builder, "no_receitas", especialista_com_agente(RECEITAS, receitas))
    return receitas


def _roteia_para(monkeypatch, *dominios):
    from frigus_ai.graph.nodes import router as router_mod

    monkeypatch.setattr(router_mod, "router_app", _FakeRoteador(Roteamento(especialistas=list(dominios))))


async def test_dois_especialistas_rodam_e_o_orquestrador_junta_os_resultados(grafo, monkeypatch):
    compilar, agentes = grafo
    receitas = _com_receitas(monkeypatch)
    _roteia_para(monkeypatch, "estoque", "receitas")
    app = compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])

    caminho, mensagens = await _rodar(app, "o que vence e que receitas tenho?")

    assert agentes["estoque"].chamadas == 1 and receitas.chamadas == 1
    assert agentes["orquestrador"].chamadas == 1  # espera os dois, uma vez só
    [pedido] = agentes["orquestrador"].entradas[0]
    assert "o que vence e que receitas tenho?" in pedido.content
    assert 'estoque:\n{"itens": ["leite"]}' in pedido.content
    assert "receitas:\nOmelete de queijo." in pedido.content
    assert caminho.count("orquestrador_node") == 1
    assert set(caminho[2:4]) == {"estoque_node", "receitas_node"}
    assert [type(m) for m in mensagens] == [HumanMessage, AIMessage]


async def test_especialista_de_texto_sozinho_nao_gasta_chamada_do_orquestrador(grafo, monkeypatch):
    compilar, agentes = grafo
    _com_receitas(monkeypatch, "Omelete de queijo.")
    _roteia_para(monkeypatch, "receitas")
    app = compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])

    saida = await app.ainvoke(EntradaGrafo(messages=[HumanMessage(content="sugira uma receita")]))

    assert agentes["orquestrador"].chamadas == 0
    assert saida["messages"][-1].content == "Omelete de queijo."  # passa pelo guardrail de saída


async def test_retentativa_de_especialista_de_texto_sozinho_chama_o_orquestrador(grafo, monkeypatch):
    compilar, agentes = grafo
    receitas = _com_receitas(monkeypatch)
    _roteia_para(monkeypatch, "receitas")
    app = compilar([
        VereditoJuiz(veredito="REPROVADO", justificativa="faltou o modo de preparo"),
        VereditoJuiz(veredito="APROVADO", justificativa="ok"),
    ])

    await app.ainvoke(EntradaGrafo(messages=[HumanMessage(content="sugira uma receita")]))

    assert receitas.chamadas == 1
    assert agentes["orquestrador"].chamadas == 1  # só na retentativa, com o pedido de revisão
    assert "faltou o modo de preparo" in agentes["orquestrador"].entradas[0][0].content


async def test_dados_dos_especialistas_nao_vazam_pro_proximo_turno(grafo, monkeypatch):
    """O checkpoint é por thread e `dados_especialistas` soma com `operator.add`: sem o
    `Overwrite([])` do guardrail de entrada, o 2º turno veria o resultado do 1º."""

    from langgraph.checkpoint.memory import MemorySaver

    compilar, _ = grafo
    _com_receitas(monkeypatch)
    compilar([VereditoJuiz(veredito="APROVADO", justificativa="ok")])
    app = builder._construir_grafo().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t-reset"}}

    await app.ainvoke(EntradaGrafo(messages=[HumanMessage(content="o que tem na geladeira?")]), config=config)
    _roteia_para(monkeypatch, "receitas")
    await app.ainvoke(EntradaGrafo(messages=[HumanMessage(content="e uma receita?")]), config=config)

    estado = (await app.aget_state(config)).values
    assert [r["agente"] for r in estado["dados_especialistas"]] == ["receitas_node"]
