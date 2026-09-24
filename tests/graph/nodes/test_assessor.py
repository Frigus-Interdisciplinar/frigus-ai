"""
Nó do Assessor (A2A) com o cliente e as fontes de dado stubadas — sem rede, Postgres nem Redis.

O que se protege: a pergunta vai pro Assessor COM os números do Frigus (é isso que dispensa a
conta do usuário lá), falta de dado não impede a pergunta, e Assessor fora do ar vira
mensagem limpa com `dados_especialista` vazio (o sinal pro builder pular o Juiz).
"""

import pytest

from frigus_ai.exceptions import AssessorIndisponivel
from frigus_ai.graph.nodes import assessor as mod
from frigus_ai.infra.postgres.context import session_context
from frigus_ai.infra.redis.ranking import ItemRanking


@pytest.fixture
def enviado(monkeypatch):
    registro = {"mensagens": []}

    async def _perguntar(mensagem, session_id):
        registro["mensagens"].append(mensagem)
        return "Reserve R$ 600,00 por mês e congele o pão."

    monkeypatch.setattr(mod.assessor, "perguntar", _perguntar)
    monkeypatch.setattr(mod, "_session_id", lambda: "chat-1")
    return registro


@pytest.fixture
def dados(monkeypatch):
    monkeypatch.setattr(
        mod.financeiro_repository, "gastos_por_mes",
        lambda stock_id, meses: {meses[0]: 580.5, meses[1]: 610.0},
    )
    monkeypatch.setattr(mod.financeiro_repository, "valor_descartado_do_mes", lambda s, m: 42.0)
    monkeypatch.setattr(
        mod.ranking, "top_desperdicio", lambda s, n: [ItemRanking("pão", 3.0), ItemRanking("alface", 2.0)]
    )


async def test_manda_a_pergunta_com_os_numeros_do_frigus(enviado, dados):
    with session_context(user_id=7, stock_id=1):
        update = await mod.no_assessor({"pergunta_original": "como economizo no mercado?"})

    [mensagem] = enviado["mensagens"]
    assert mensagem.startswith("como economizo no mercado?")
    assert "R$ 580,50" in mensagem and "R$ 610,00" in mensagem
    assert "R$ 42,00" in mensagem
    assert "pão (3x)" in mensagem
    assert "conta de serviço" in mensagem  # não misturar a conta de lá com o usuário

    assert update["resposta_especialista"] == "Reserve R$ 600,00 por mês e congele o pão."
    assert "R$ 580,50" in update["dados_especialista"]  # o Juiz confere contra os números enviados


async def test_sem_estoque_na_sessao_pergunta_sem_dados(enviado):
    update = await mod.no_assessor({"pergunta_original": "como economizo no mercado?"})

    assert enviado["mensagens"] == ["como economizo no mercado?"]
    assert update["dados_especialista"]  # respondeu: não é o sinal de indisponível


async def test_assessor_fora_do_ar_devolve_mensagem_limpa(monkeypatch, dados):
    async def _fora(mensagem, session_id):
        raise AssessorIndisponivel("connection refused")

    monkeypatch.setattr(mod.assessor, "perguntar", _fora)
    monkeypatch.setattr(mod, "_session_id", lambda: "chat-1")

    with session_context(user_id=7, stock_id=1):
        update = await mod.no_assessor({"pergunta_original": "como economizo?"})

    assert update["resposta_especialista"] == mod.INDISPONIVEL
    assert update["dados_especialista"] == ""
