"""Guardrail de saída — o filtro barato decide se a revisão de compliance chama o LLM."""

import pytest
from langchain_core.messages import AIMessage

from frigus_ai.graph.guardrail import saida as mod
from frigus_ai.graph.guardrail.saida import guardrail_saida, precisa_revisao


class _FakeLLM:
    def __init__(self, texto):
        self._texto = texto
        self.chamadas = 0

    async def ainvoke(self, _entrada):
        self.chamadas += 1
        return AIMessage(content=self._texto)


@pytest.mark.parametrize(
    "resposta",
    [
        "O frango está seguro para consumo, pode comer sem medo.",
        "Pode confiar 100%, esse queijo nunca vai estragar.",
        "Pra sua dieta de diabetes, corte o arroz.",
        "Com certeza ainda dá pra usar.",
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
    llm = _FakeLLM("RESPOSTA: não deveria aparecer")
    monkeypatch.setattr(mod, "llm_rapido", llm)

    resultado = await guardrail_saida("Você tem 2 caixas de leite.", {})

    assert resultado["conteudo"] == "Você tem 2 caixas de leite."
    assert llm.chamadas == 0


async def test_resposta_de_risco_usa_a_revisao_do_llm(monkeypatch):
    llm = _FakeLLM("STATUS: CORRIGIDO\nRESPOSTA:\nConfira cheiro e aparência antes de consumir.")
    monkeypatch.setattr(mod, "llm_rapido", llm)

    resultado = await guardrail_saida("Pode confiar 100%, está bom.", {})

    assert resultado["conteudo"] == "Confira cheiro e aparência antes de consumir."
    assert llm.chamadas == 1
