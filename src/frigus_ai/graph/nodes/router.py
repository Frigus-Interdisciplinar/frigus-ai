from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from frigus_ai.graph.agents import router_app
from frigus_ai.graph.names import ROTEADOR
from frigus_ai.graph.state import (
    Estado,
    Roteamento,
    Route,
    RouterUpdate,
)
from frigus_ai.logging import Logging
from frigus_ai.observability.metrics import ROUTER_DECISIONS, medir_node

log = Logging.get_logger(__name__)

_NAO_ENTENDI = (
    "Não consegui entender o pedido. Posso ajudar com seu estoque, lista de compras, "
    "receitas ou os gastos com alimentação — pode reformular?"
)


async def _rotear(mensagens: Sequence[AnyMessage]) -> Roteamento:
    """Falha de chamada ou saída fora do schema vira `fim` com resposta genérica — o turno
    nunca cai por causa do roteador."""

    try:
        saida = await router_app.ainvoke({"messages": list(mensagens)})
        roteamento = saida["structured_response"]
    except Exception as e:
        log.warning(f"Roteador falhou, respondendo sem especialista: {e}")
        return Roteamento(rota=Route.FIM, resposta=_NAO_ENTENDI)

    assert isinstance(roteamento, Roteamento)
    return roteamento


def _ultima_pergunta(mensagens: Sequence[AnyMessage]) -> str:
    """A mensagem do usuário como chegou (já anonimizada pelo guardrail) — em vez de pedir
    pro LLM repeti-la "sem edições" e torcer."""

    for msg in reversed(mensagens):
        if isinstance(msg, HumanMessage):
            return msg.text
    return ""


@medir_node(ROTEADOR)
async def no_roteador(estado: Estado) -> RouterUpdate:

    roteamento = await _rotear(estado["messages"])
    pergunta   = _ultima_pergunta(estado["messages"])

    log.debug(f"Rota escolhida: {roteamento.rota} | pergunta: '{pergunta}'")
    ROUTER_DECISIONS.labels(route=roteamento.rota).inc()

    if roteamento.rota == Route.FIM:
        return RouterUpdate(
            agentes_chamados=[ROTEADOR],
            rota=Route.FIM,
            pergunta_original=pergunta,
            messages=[AIMessage(content=roteamento.resposta or _NAO_ENTENDI)],
        )

    return RouterUpdate(
        agentes_chamados=[ROTEADOR],
        rota=roteamento.rota,
        pergunta_original=pergunta,
        tentativas_juiz=0,
    )


__all__ = ["no_roteador"]
