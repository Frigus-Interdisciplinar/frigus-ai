"""
Streaming e extração da resposta final, sem grafo real.

O ponto delicado é que os nós devolvem a mensagem final ora como `AIMessage`
(estado consolidado do `ainvoke`), ora como dict cru (delta do `astream`) — se o
extrator só entendesse uma das formas, o SSE terminaria sempre com "Sem resposta".
"""

from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.chat import runner


class _FakeGrafo:
    def __init__(self, updates):
        self._updates = updates

    async def astream(self, estado, config, stream_mode):
        for update in self._updates:
            yield update


def _usar_grafo(monkeypatch, updates):
    monkeypatch.setattr(runner, "fluxo_agentes", lambda: _FakeGrafo(updates))


def test_extrair_resposta_aceita_aimessage_e_dict():
    assert runner._extrair_resposta({"messages": [AIMessage(content="via objeto")]}) == "via objeto"
    assert runner._extrair_resposta(
        {"messages": [{"role": "assistant", "content": "via dict"}]}
    ) == "via dict"


def test_extrair_resposta_ignora_mensagem_do_humano():
    estado = {"messages": [AIMessage(content="antiga"), HumanMessage(content="pergunta")]}

    assert runner._extrair_resposta(estado) == "antiga"


def test_extrair_resposta_sem_mensagens():
    assert runner._extrair_resposta({}) is None


async def test_stream_emite_um_evento_por_no_e_a_resposta_no_fim(monkeypatch):
    _usar_grafo(monkeypatch, [
        {"guardrail_entrada_node": {"messages": [HumanMessage(content="oi")]}},
        {"roteador_node": {"rota": "estoque"}},
        {"estoque_node": {"resposta_especialista": "cru"}},
        {"guardrail_saida_node": {"messages": [{"role": "assistant", "content": "resposta final"}]}},
    ])

    eventos = [e async for e in runner.executar_stream("oi", "sessao", 1, 1, "")]

    assert [nome for tipo, nome in eventos if tipo == "no"] == [
        "guardrail_entrada_node", "roteador_node", "estoque_node", "guardrail_saida_node"
    ]
    assert eventos[-1] == ("resposta", "resposta final")


async def test_stream_usa_a_ultima_resposta_quando_o_grafo_para_antes_do_fim(monkeypatch):
    """Guardrail de entrada bloqueando: o grafo termina sem passar pelo de saída."""

    _usar_grafo(monkeypatch, [
        {"guardrail_entrada_node": {"messages": [{"role": "assistant", "content": "bloqueado"}]}},
    ])

    eventos = [e async for e in runner.executar_stream("oi", "sessao", 1, 1, "")]

    assert eventos[-1] == ("resposta", "bloqueado")


async def test_stream_sem_nenhuma_resposta_nao_devolve_none(monkeypatch):
    _usar_grafo(monkeypatch, [{"roteador_node": {"rota": "fim"}}])

    eventos = [e async for e in runner.executar_stream("oi", "sessao", 1, 1, "")]

    assert eventos[-1] == ("resposta", "Sem resposta.")
