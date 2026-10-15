from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.runtime import Runtime

from frigus_ai.graph.agents import router_app
from frigus_ai.graph.names import ROTEADOR
from frigus_ai.graph.state import (
    ContextoPrompt,
    Estado,
    Roteamento,
    Route,
    RouterUpdate,
)
from frigus_ai.infra.logging import Logging
from frigus_ai.telemetry import medir_node
from frigus_ai.telemetry.metrics import ROUTER_DECISIONS

log = Logging.get_logger(__name__)

_NAO_ENTENDI = (
    "Não consegui entender o pedido. Posso ajudar com seu estoque, lista de compras, "
    "receitas ou os gastos com alimentação — pode reformular?"
)


async def _rotear(mensagens: Sequence[AnyMessage], contexto: ContextoPrompt) -> Roteamento:
    """Falha de chamada ou saída fora do schema vira resposta genérica sem especialista — o turno
    nunca cai por causa do roteador."""

    try:
        saida = await router_app.ainvoke({"messages": list(mensagens)}, context=contexto)
        roteamento = saida["structured_response"]
    except Exception as e:
        log.warning("Roteador falhou, respondendo sem especialista: %s", e)
        return Roteamento(resposta=_NAO_ENTENDI)

    if not isinstance(roteamento, Roteamento):
        raise TypeError(f"esperava Roteamento, veio {type(roteamento).__name__}")
    return roteamento


@medir_node(ROTEADOR)
async def no_roteador(estado: Estado, runtime: Runtime[ContextoPrompt]) -> RouterUpdate:
    roteamento = await _rotear(estado["messages"], runtime.context)

    # Sem repetição (o LLM pode listar o mesmo domínio duas vezes), mantendo a ordem.
    especialistas = list(dict.fromkeys(roteamento.especialistas))

    log.debug("Especialistas escolhidos: %s", especialistas or "nenhum (resposta direta)")
    for dominio in especialistas or [Route.FIM]:
        ROUTER_DECISIONS.labels(route=dominio).inc()

    if not especialistas:
        return RouterUpdate(
            agentes_chamados=[ROTEADOR],
            especialistas=[],
            messages=[AIMessage(content=roteamento.resposta or _NAO_ENTENDI)],
        )

    return RouterUpdate(agentes_chamados=[ROTEADOR], especialistas=especialistas)


__all__ = ["no_roteador"]
