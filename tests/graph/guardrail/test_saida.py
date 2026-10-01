"""Guardrail de saída — o filtro barato decide se a revisão de compliance chama o LLM."""

import pytest

from frigus_ai.graph.guardrail import saida as mod
from frigus_ai.graph.guardrail.saida import guardrail_saida, precisa_revisao
from frigus_ai.graph.guardrail.schemas import RevisaoCompliance


class _FakeLLM:
    def __init__(self, resultado):
        self._resultado = resultado
        self.chamadas = 0

    async def ainvoke(self, _entrada):
        self.chamadas += 1
        if isinstance(self._resultado, Exception):
            raise self._resultado
        return self._resultado


@pytest.mark.parametrize(
    "resposta",
    [
        "O frango está seguro para consumo, pode comer sem medo.",
        "Pode confiar 100%, esse queijo nunca vai estragar.",
        "Pra sua dieta de diabetes, corte o arroz.",
        "Com certeza ainda dá pra usar.",
        "Isso melhora a composição corporal.",
        "O índice glicêmico dessa fruta é baixo.",
    ],
)
def test_resposta_de_risco_pede_revisao(resposta):
    assert precisa_revisao(resposta) is True


@pytest.mark.parametrize(
    "resposta",
    [
        "Você tem 2 caixas de leite na geladeira.",
        "Adicionei arroz e feijão na sua lista de compras.",
        "Este mês você desperdiçou R$ 42,00 em alimentos.",
    ],
)
def test_resposta_limpa_nao_pede_revisao(resposta):
    assert precisa_revisao(resposta) is False


async def test_resposta_limpa_nao_chama_llm(monkeypatch):
    llm = _FakeLLM(RevisaoCompliance(revisada="não deveria aparecer", modificada=True))
    monkeypatch.setattr(mod, "llm_revisor", llm)

    resultado = await guardrail_saida("Você tem 2 caixas de leite.", {})

    assert resultado["conteudo"] == "Você tem 2 caixas de leite."
    assert llm.chamadas == 0


async def test_resposta_de_risco_usa_a_revisao_do_llm(monkeypatch):
    llm = _FakeLLM(
        RevisaoCompliance(revisada="Confira cheiro e aparência antes de consumir.", modificada=True)
    )
    monkeypatch.setattr(mod, "llm_revisor", llm)

    resultado = await guardrail_saida("Pode confiar 100%, está bom.", {})

    assert resultado["conteudo"] == "Confira cheiro e aparência antes de consumir."
    assert llm.chamadas == 1


@pytest.mark.parametrize("falha", [RuntimeError("provider fora"), "texto solto"])
async def test_falha_ou_saida_fora_do_schema_mantem_a_resposta_original(monkeypatch, falha):
    monkeypatch.setattr(mod, "llm_revisor", _FakeLLM(falha))

    resultado = await guardrail_saida("Pode confiar 100%, está bom.", {})

    assert resultado["conteudo"] == "Pode confiar 100%, está bom."
