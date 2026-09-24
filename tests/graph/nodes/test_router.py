"""
Roteador com saída estruturada (`Roteamento`), agente stubado — sem LLM.

O que se protege: rota de especialista não responde ao usuário, `fim` responde com o texto do
roteador, e falha do LLM (chamada ou schema) nunca derruba o turno.
"""

from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.graph.nodes import router as mod
from frigus_ai.graph.state import Roteamento


class _FakeRoteador:
    def __init__(self, resultado):
        self._resultado = resultado

    async def ainvoke(self, entrada):
        if isinstance(self._resultado, Exception):
            raise self._resultado
        return {"messages": entrada["messages"], "structured_response": self._resultado}


def _estado(*textos):
    return {"messages": [HumanMessage(content=t) for t in textos]}


async def test_rota_de_especialista_nao_responde_e_guarda_a_pergunta(monkeypatch):
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(Roteamento(rota="estoque")))

    update = await mod.no_roteador(_estado("oi", "o que vence essa semana?"))

    assert update["rota"] == "estoque"
    assert update["pergunta_original"] == "o que vence essa semana?"
    assert update["tentativas_juiz"] == 0
    assert "messages" not in update


async def test_fim_responde_com_o_texto_do_roteador(monkeypatch):
    monkeypatch.setattr(
        mod, "router_app", _FakeRoteador(Roteamento(rota="fim", resposta="Olá! Por onde começamos?"))
    )

    update = await mod.no_roteador(_estado("oi"))

    assert update["rota"] == "fim"
    assert update["messages"] == [AIMessage(content="Olá! Por onde começamos?")]


async def test_fim_sem_resposta_usa_a_generica(monkeypatch):
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(Roteamento(rota="fim")))

    update = await mod.no_roteador(_estado("hm"))

    assert update["messages"][0].content == mod._NAO_ENTENDI


async def test_falha_do_llm_vira_fim_sem_derrubar_o_turno(monkeypatch):
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(ValueError("saída fora do schema")))

    update = await mod.no_roteador(_estado("qual o sentido da vida?"))

    assert update["rota"] == "fim"
    assert update["messages"][0].content == mod._NAO_ENTENDI
