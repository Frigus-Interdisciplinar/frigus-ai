"""JeV pelo gateway, com o HTTP stubado: o contrato do pedido e a validação das respostas."""

import json
from enum import StrEnum

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from frigus_ai.infra.llm import jev
from frigus_ai.infra.llm.jev import client
from frigus_ai.infra.llm.jev.schemas import PerguntaEscolha, PerguntaPredicado
from frigus_ai.settings import settings
from frigus_ai.telemetry.metrics import JEV_DECISIONS


class _Cor(StrEnum):
    AZUL = "AZUL"
    VERDE = "VERDE"


_OPCOES = {_Cor.AZUL: "cor do céu", _Cor.VERDE: "cor da folha"}


@pytest.fixture
def gateway(monkeypatch):
    """Responde `/decisions` com `corpo` e guarda o pedido enviado em `pedidos`."""

    pedidos, corpo = [], {"model": "typesafe-ai/jev", "answers": [], "usage": {"input_tokens": 50}}
    cliente_real = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(json.loads(request.content))
        return httpx.Response(200, json=corpo)

    monkeypatch.setattr(settings.llm.gateway, "api_key", SecretStr("fake"))
    monkeypatch.setattr(
        client.httpx, "AsyncClient",
        lambda **kw: cliente_real(transport=httpx.MockTransport(handler), **kw),
    )
    return pedidos, corpo


async def test_escolher_devolve_a_opcao_tipada_e_manda_as_opcoes_com_reserva(gateway):
    pedidos, corpo = gateway
    corpo["answers"] = [{"type": "choice", "name": "escolha", "choice": "VERDE", "confidence": 0.9}]
    decisoes = JEV_DECISIONS.labels(uso="teste", pergunta="escolha", escolha="VERDE", modelo="typesafe-ai/jev")
    antes = decisoes._value.get()

    escolha = await jev.escolher("teste", "de que cor é a grama?", "escolha a cor", _OPCOES)

    assert escolha is _Cor.VERDE
    assert decisoes._value.get() == antes + 1
    [pergunta] = pedidos[0]["questions"]
    assert pergunta["type"] == "choice"
    assert [c["value"] for c in pergunta["choices"]] == ["AZUL", "VERDE"]
    assert pedidos[0]["providerOptions"]["gateway"]["models"] == ["openai/gpt-6-luna-decisions"]


async def test_decidir_faz_varias_perguntas_numa_requisicao(gateway):
    pedidos, corpo = gateway
    corpo["answers"] = [
        {"type": "predicate", "name": "estoque", "probability": 0.8},
        {"type": "predicate", "name": "compras", "probability": 0.1},
        {"type": "choice", "name": "cor", "choice": "AZUL"},
    ]

    decisoes = await jev.decidir("teste", "entrada", [
        PerguntaPredicado(name="estoque", instructions="precisa de estoque?"),
        PerguntaPredicado(name="compras", instructions="precisa de compras?"),
        PerguntaEscolha(name="cor", instructions="qual cor?", choices=_OPCOES),
    ])

    assert decisoes.sim("estoque") and not decisoes.sim("compras")
    assert decisoes.escolha("cor") == "AZUL"
    assert [q["type"] for q in pedidos[0]["questions"]] == ["predicate", "predicate", "choice"]


@pytest.mark.parametrize(
    "answer",
    [{"type": "refusal", "name": "escolha"}, {"type": "choice", "name": "escolha", "choice": "ROXO"}],
)
async def test_recusa_ou_opcao_fora_da_lista_levanta(gateway, answer):
    _, corpo = gateway
    corpo["answers"] = [answer]

    with pytest.raises(ValueError):
        await jev.escolher("teste", "oi", "escolha a cor", _OPCOES)


async def test_corpo_fora_do_contrato_levanta(gateway):
    _, corpo = gateway
    del corpo["usage"]

    with pytest.raises(ValidationError):
        await jev.escolher("teste", "oi", "escolha a cor", _OPCOES)
