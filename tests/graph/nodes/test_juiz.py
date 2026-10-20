"""Juiz com structured output: falha na chamada ou saída fora do schema segue como INDISPONIVEL (falha aberta, sem fingir aprovação)."""

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
    assert update["reescritas_juiz"] == 1


async def test_reprovado_sem_tentativas_sobrando_segue_sem_feedback(monkeypatch):
    monkeypatch.setattr(
        mod, "llm_avaliador", _FakeLLM(VereditoJuiz(veredito="REPROVADO", justificativa="x"))
    )

    update = await no_juiz(_estado(reescritas_juiz=mod.MAX_REESCRITAS))

    assert update["feedback_juiz"] == ""
    assert update["reescritas_juiz"] == mod.MAX_REESCRITAS


@pytest.mark.parametrize("falha", [RuntimeError("provider fora"), "texto solto"])
async def test_falha_ou_saida_fora_do_schema_fica_indisponivel(monkeypatch, falha):
    monkeypatch.setattr(mod, "llm_avaliador", _FakeLLM(falha))

    update = await no_juiz(_estado())

    assert update["veredito_juiz"] == "INDISPONIVEL"
    assert update["feedback_juiz"] == ""


async def test_jev_reprova_com_feedback_de_cada_criterio(monkeypatch):
    _jev_avalia(monkeypatch, mod.Grounding.SEM_EVIDENCIA, completa=False)

    update = await no_juiz(_estado())

    assert update["veredito_juiz"] == "REPROVADO"
    feedback = mod._FEEDBACK
    assert update["feedback_juiz"] == f"{feedback[mod.Grounding.SEM_EVIDENCIA]} {feedback[mod.Criterio.COMPLETUDE]}"
    assert update["reescritas_juiz"] == 1


async def test_jev_falhando_cai_no_juiz_llm(monkeypatch):
    async def falha(*_args):
        raise RuntimeError("gateway fora")

    monkeypatch.setattr(mod.jev, "disponivel", lambda: True)
    monkeypatch.setattr(mod.jev, "decidir", falha)
    monkeypatch.setattr(mod, "llm_avaliador", _FakeLLM(VereditoJuiz(veredito="APROVADO", justificativa="ok")))

    update = await no_juiz(_estado())

    assert update["veredito_juiz"] == "APROVADO"
    assert update["justificativa_juiz"] == "ok"
