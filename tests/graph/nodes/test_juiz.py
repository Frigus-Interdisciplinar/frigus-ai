"""Juiz com structured output: falha na chamada ou saída fora do schema aprova (falha aberta)."""

import pytest
from langchain_core.messages import HumanMessage

from frigus_ai.graph.nodes import juiz as mod
from frigus_ai.graph.nodes.juiz import VereditoJuiz, no_juiz


class _FakeLLM:
    def __init__(self, resultado):
        self._resultado = resultado

    async def ainvoke(self, _entrada):
        if isinstance(self._resultado, Exception):
            raise self._resultado
        return self._resultado


def _estado(**extra):
    return {"messages": [HumanMessage(content="oi")], **extra}


async def test_reprovado_devolve_feedback_e_conta_tentativa(monkeypatch):
    monkeypatch.setattr(
        mod, "llm_avaliador", _FakeLLM(VereditoJuiz(veredito="REPROVADO", justificativa="citou iogurte"))
    )

    update = await no_juiz(_estado())

    assert update["veredito_juiz"] == "REPROVADO"
    assert update["feedback_juiz"] == "citou iogurte"
    assert update["tentativas_juiz"] == 1


async def test_reprovado_sem_tentativas_sobrando_segue_sem_feedback(monkeypatch):
    monkeypatch.setattr(
        mod, "llm_avaliador", _FakeLLM(VereditoJuiz(veredito="REPROVADO", justificativa="x"))
    )

    update = await no_juiz(_estado(tentativas_juiz=mod.MAX_TENTATIVAS))

    assert update["feedback_juiz"] == ""
    assert update["tentativas_juiz"] == mod.MAX_TENTATIVAS


@pytest.mark.parametrize("falha", [RuntimeError("provider fora"), "texto solto"])
async def test_falha_ou_saida_fora_do_schema_aprova(monkeypatch, falha):
    monkeypatch.setattr(mod, "llm_avaliador", _FakeLLM(falha))

    update = await no_juiz(_estado())

    assert update["veredito_juiz"] == "APROVADO"
    assert update["feedback_juiz"] == ""
