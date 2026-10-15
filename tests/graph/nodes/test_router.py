"""
Roteador com saída estruturada (`Roteamento`), agente stubado — sem LLM.

O que se protege: especialista não faz o roteador responder ao usuário, lista vazia responde com o
texto do roteador, domínios repetidos viram um só, e falha do LLM (chamada ou schema) nunca derruba
o turno.
"""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.graph.nodes import router as mod
from frigus_ai.graph.state import ContextoPrompt, Roteamento

_RUNTIME = SimpleNamespace(context=ContextoPrompt())


class _FakeRoteador:
    def __init__(self, resultado):
        self._resultado = resultado

    async def ainvoke(self, entrada, **_kwargs):
        if isinstance(self._resultado, Exception):
            raise self._resultado
        return {"messages": entrada["messages"], "structured_response": self._resultado}


def _estado(*textos):
    return {"messages": [HumanMessage(content=t) for t in textos]}


async def test_especialista_nao_responde_ao_usuario(monkeypatch):
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(Roteamento(especialistas=["estoque"])))

    update = await mod.no_roteador(_estado("oi", "o que vence essa semana?"), _RUNTIME)

    assert update["especialistas"] == ["estoque"]
    assert "messages" not in update


async def test_varios_especialistas_sem_repeticao_e_na_ordem(monkeypatch):
    escolha = Roteamento(especialistas=["receitas", "estoque", "receitas"])
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(escolha))

    update = await mod.no_roteador(_estado("vence algo? e receitas?"), _RUNTIME)

    assert update["especialistas"] == ["receitas", "estoque"]


async def test_lista_vazia_responde_com_o_texto_do_roteador(monkeypatch):
    monkeypatch.setattr(
        mod, "router_app", _FakeRoteador(Roteamento(resposta="Olá! Por onde começamos?"))
    )

    update = await mod.no_roteador(_estado("oi"), _RUNTIME)

    assert update["especialistas"] == []
    assert update["messages"] == [AIMessage(content="Olá! Por onde começamos?")]


async def test_lista_vazia_sem_resposta_usa_a_generica(monkeypatch):
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(Roteamento()))

    update = await mod.no_roteador(_estado("hm"), _RUNTIME)

    assert update["messages"][0].content == mod._NAO_ENTENDI


async def test_falha_do_llm_responde_generico_sem_derrubar_o_turno(monkeypatch):
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(ValueError("saída fora do schema")))

    update = await mod.no_roteador(_estado("qual o sentido da vida?"), _RUNTIME)

    assert update["especialistas"] == []
    assert update["messages"][0].content == mod._NAO_ENTENDI
