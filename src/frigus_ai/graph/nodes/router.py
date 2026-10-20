from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.runtime import Runtime

from frigus_ai.graph.agents import router_app
from frigus_ai.graph.names import ROTEADOR
from frigus_ai.graph.prompts import load_sections
from frigus_ai.graph.state import (
    ContextoPrompt,
    Estado,
    RotaEspecialista,
    Roteamento,
    Route,
    RouterUpdate,
)
from frigus_ai.infra.llm import jev
from frigus_ai.infra.llm.jev.schemas import PerguntaPredicado
from frigus_ai.infra.logging import Logging
from frigus_ai.telemetry import medir_node
from frigus_ai.telemetry.metrics import ROUTER_DECISIONS

log = Logging.get_logger(__name__)

_NAO_ENTENDI = (
    "Não consegui entender o pedido. Posso ajudar com seu estoque, lista de compras, "
    "receitas ou os gastos com alimentação — pode reformular?"
)

DESCRICAO_ESPECIALISTA: dict[RotaEspecialista, str] = {
    "estoque":    "itens da geladeira/freezer/despensa, validade, consumo e descarte",
    "compras":    "lista de compras, itens em falta e registro de compras",
    "receitas":   "sugestão de receitas e preferências alimentares (gostos, alergias)",
    "financeiro": "consultar números da comida: quanto gastou, comparação entre meses, desperdício em reais",
    "assessor":   "conselho ou plano para gastar ou desperdiçar menos com comida",
    "faq":        "dúvidas sobre o funcionamento, planos e limitações do Frigus",
}

_PROMPTS = load_sections("router.md")


def _ultima_pergunta(mensagens: Sequence[AnyMessage]) -> str:
    return next(m.text for m in reversed(mensagens) if isinstance(m, HumanMessage))


async def _rotear_com_jev(mensagens: Sequence[AnyMessage]) -> list[RotaEspecialista] | None:
    """Os especialistas que o JeV aprovou olhando só a última pergunta, ou None quando o pedido
    precisa do LLM: nenhum especialista (saudação, fora de escopo, resposta a uma clarificação que
    só faz sentido com o histórico) ou etapas que dependem uma da outra."""

    perguntas = [
        PerguntaPredicado(name=dominio, instructions=_PROMPTS["especialista_jev"].format(dominio=dominio, descricao=descricao))
        for dominio, descricao in DESCRICAO_ESPECIALISTA.items()
    ]
    perguntas.append(PerguntaPredicado(name="etapas", instructions=_PROMPTS["etapas_jev"]))

    decisoes = await jev.decidir("roteador", _ultima_pergunta(mensagens), perguntas)
    especialistas = [dominio for dominio in DESCRICAO_ESPECIALISTA if decisoes.sim(dominio)]

    if not especialistas or decisoes.sim("etapas"):
        return None
    return especialistas


async def _rotear(mensagens: Sequence[AnyMessage], contexto: ContextoPrompt) -> Roteamento:
    """JeV decide quem atende; o LLM entra quando é preciso escrever a resposta. Falha de chamada
    ou saída fora do schema vira resposta genérica — o turno nunca cai por causa do roteador."""

    if jev.disponivel():
        try:
            if especialistas := await _rotear_com_jev(mensagens):
                return Roteamento(especialistas=especialistas)
        except Exception as e:
            log.warning("Roteador JeV falhou, usando o LLM: %s", e)

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
            especialistas=[],
            messages=[AIMessage(content=roteamento.resposta or _NAO_ENTENDI)],
        )

    return RouterUpdate(especialistas=especialistas)


__all__ = ["no_roteador"]
