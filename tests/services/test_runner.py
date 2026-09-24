"""
Streaming e extração da resposta final, sem grafo real.

O ponto delicado é achar a última mensagem de IA tanto no estado consolidado do `ainvoke`
quanto no delta de um nó vindo do `astream` — se o extrator errasse, o SSE terminaria
sempre com "Sem resposta".
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.graph.agents import conversas_anteriores
from frigus_ai.repositories import chat_embeddings_repository
from frigus_ai.schemas.execution import AnswerReady, NodeStarted, RunFinished
from frigus_ai.services import runner


@pytest.fixture(autouse=True)
def _sem_qdrant(monkeypatch):
    """A busca de conversas anteriores roda antes do grafo — sem isso, iria à rede."""

    async def _buscar(user_id, pergunta, session_id_atual):
        return ["comprou leite semana passada"]

    monkeypatch.setattr(chat_embeddings_repository, "buscar_resumos_relevantes", _buscar)


async def test_conversas_anteriores_ficam_disponiveis_pro_prompt():
    await runner._carregar_conversas_anteriores("e o leite?", "chat-1", 7, imagem_b64=None)
    assert conversas_anteriores.get() == ("comprou leite semana passada",)

    # Turno com foto não busca — e não herda o valor do turno anterior.
    await runner._carregar_conversas_anteriores("foto", "chat-1", 7, imagem_b64="abc")
    assert conversas_anteriores.get() == ()


class _FakeGrafo:
    """
    Emula o formato de `astream_events(version="v2")`: um `on_chain_start` seguido de
    `on_chain_end` (com `output` = o update que o node devolveu) por node — o mesmo
    shape que `runner.executar_stream` filtra por nome (`_NOMES_DE_NODE`).
    """

    def __init__(self, updates):
        self._updates = updates

    async def astream_events(self, estado, config, version):
        for update in self._updates:
            for nome, output in update.items():
                yield {"event": "on_chain_start", "name": nome, "data": {}}
                yield {"event": "on_chain_end", "name": nome, "data": {"output": output}}


class _FakeFluxoAgentes:
    def __init__(self, grafo):
        self._grafo = grafo

    async def get(self):
        return self._grafo


def _usar_grafo(monkeypatch, updates):
    monkeypatch.setattr(runner, "fluxo_agentes", _FakeFluxoAgentes(_FakeGrafo(updates)))


def test_extrair_resposta_pega_a_ultima_aimessage():
    estado = {"messages": [AIMessage(content="antiga"), AIMessage(content="mais nova")]}

    assert runner._extrair_resposta(estado) == "mais nova"


def test_extrair_resposta_ignora_mensagem_do_humano():
    estado = {"messages": [AIMessage(content="antiga"), HumanMessage(content="pergunta")]}

    assert runner._extrair_resposta(estado) == "antiga"


def test_extrair_resposta_sem_mensagens():
    assert runner._extrair_resposta({}) is None


def test_estado_inicial_sem_imagem_nao_tem_a_chave():
    estado = runner._estado_inicial("oi", 1)

    assert "imagem_b64" not in estado


def test_estado_inicial_com_imagem_inclui_a_chave():
    estado = runner._estado_inicial("analise a foto", 1, imagem_b64="ZmFrZQ==")

    assert estado["imagem_b64"] == "ZmFrZQ=="


async def test_stream_emite_um_evento_por_no_e_a_resposta_no_fim(monkeypatch):
    _usar_grafo(monkeypatch, [
        {"guardrail_entrada_node": {"messages": [HumanMessage(content="oi")]}},
        {"roteador_node": {"rota": "estoque"}},
        {"estoque_node": {"resposta_especialista": "cru"}},
        {"guardrail_saida_node": {"messages": [AIMessage(content="resposta final")]}},
    ])

    eventos = [e async for e in runner.executar_stream("oi", "sessao", 1, 1)]

    nos_iniciados = [e.node for e in eventos if isinstance(e, NodeStarted)]
    assert nos_iniciados == [
        "guardrail_entrada_node", "roteador_node", "estoque_node", "guardrail_saida_node"
    ]
    assert AnswerReady(content="resposta final") in eventos
    assert isinstance(eventos[-1], RunFinished)


async def test_stream_usa_a_ultima_resposta_quando_o_grafo_para_antes_do_fim(monkeypatch):
    """Guardrail de entrada bloqueando: o grafo termina sem passar pelo de saída."""

    _usar_grafo(monkeypatch, [
        {"guardrail_entrada_node": {"messages": [AIMessage(content="bloqueado")]}},
    ])

    eventos = [e async for e in runner.executar_stream("oi", "sessao", 1, 1)]

    assert AnswerReady(content="bloqueado") in eventos
    assert isinstance(eventos[-1], RunFinished)


async def test_stream_sem_nenhuma_resposta_nao_devolve_answer_ready(monkeypatch):
    _usar_grafo(monkeypatch, [{"roteador_node": {"rota": "fim"}}])

    eventos = [e async for e in runner.executar_stream("oi", "sessao", 1, 1)]

    assert not any(isinstance(e, AnswerReady) for e in eventos)
    assert isinstance(eventos[-1], RunFinished)
