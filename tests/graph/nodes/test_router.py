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


# --------------------- JeV decide quem atende ---------------------

def _jev_responde(monkeypatch, sim: set[str]):
    """Liga o JeV e responde `sim` pros predicados listados, `não` pro resto."""

    from frigus_ai.infra.llm.jev import Decisoes
    from frigus_ai.infra.llm.jev.schemas import Predicado

    chamada = SimpleNamespace(entrada=None, perguntas=[])

    async def decidir(uso, entrada, perguntas):
        chamada.entrada = entrada
        chamada.perguntas = [p.name for p in perguntas]
        return Decisoes({
            p.name: Predicado(type="predicate", name=p.name, probability=0.9 if p.name in sim else 0.1)
            for p in perguntas
        })

    monkeypatch.setattr(mod.jev, "disponivel", lambda: True)
    monkeypatch.setattr(mod.jev, "decidir", decidir)
    return chamada


async def test_jev_escolhe_os_especialistas_sem_chamar_o_llm(monkeypatch):
    perguntas = _jev_responde(monkeypatch, {"estoque", "receitas"})
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(AssertionError("não devia chamar o LLM")))

    update = await mod.no_roteador(_estado("o que vence e que receitas faço?"), _RUNTIME)

    assert update["especialistas"] == ["estoque", "receitas"]
    assert set(perguntas.perguntas) == {*mod.DESCRICAO_ESPECIALISTA, "etapas"}


async def test_sem_especialista_ou_com_etapas_o_llm_responde(monkeypatch):
    llm = _FakeRoteador(Roteamento(resposta="Vamos em duas etapas."))
    monkeypatch.setattr(mod, "router_app", llm)

    for sim in (set(), {"estoque", "etapas"}):
        _jev_responde(monkeypatch, sim)
        update = await mod.no_roteador(_estado("adicione leite e sugira receitas"), _RUNTIME)
        assert update["messages"] == [AIMessage(content="Vamos em duas etapas.")]


async def test_jev_falhando_cai_no_llm(monkeypatch):
    async def falha(*_args):
        raise RuntimeError("gateway fora")

    monkeypatch.setattr(mod.jev, "disponivel", lambda: True)
    monkeypatch.setattr(mod.jev, "decidir", falha)
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(Roteamento(especialistas=["compras"])))

    update = await mod.no_roteador(_estado("o que falta comprar?"), _RUNTIME)

    assert update["especialistas"] == ["compras"]


async def test_jev_recebe_so_a_ultima_pergunta_do_usuario(monkeypatch):
    perguntas = _jev_responde(monkeypatch, {"estoque"})
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(AssertionError("não devia chamar o LLM")))
    estado = {"messages": [
        HumanMessage(content="quero receitas"),
        AIMessage(content="Aqui estão 5 receitas bem compridas..."),
        HumanMessage(content="o que vence essa semana?"),
    ]}

    await mod.no_roteador(estado, _RUNTIME)

    assert perguntas.entrada == "o que vence essa semana?"


async def test_pedido_com_duas_consultas_independentes_roteia_pros_dois(monkeypatch):
    _jev_responde(monkeypatch, {"receitas", "compras"})
    monkeypatch.setattr(mod, "router_app", _FakeRoteador(AssertionError("não devia chamar o LLM")))

    update = await mod.no_roteador(
        _estado("me sugira uma receita com batata frita e já veja o que está na minha lista de compras"),
        _RUNTIME,
    )

    assert update["especialistas"] == ["compras", "receitas"]
