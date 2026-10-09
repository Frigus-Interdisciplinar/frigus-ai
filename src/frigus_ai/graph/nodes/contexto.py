"""
Glue entre os nós do grafo e os modelos (agentes ou LLMs crus).

Agente devolve `{"messages": [...]}` e LLM cru devolve uma `AIMessage`; `responder` e `perguntar`
garantem que o conteúdo é texto (resposta multimodal vazava como lista de blocos).
`mensagens_do_turno` monta a entrada do especialista, com o feedback do Juiz quando reprovou.
"""

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.runnables import Runnable

from frigus_ai.graph.state import ContextoPrompt, Estado
from frigus_ai.infra.logging import Logging
from frigus_ai.settings import settings

logger = Logging.get_logger(__name__)


class RespostaAgenteInvalida(RuntimeError):
    pass


def _texto(conteudo: Any) -> str:
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        partes: list[str] = []
        for item in conteudo:
            if isinstance(item, str):
                partes.append(item)
            elif isinstance(item, dict) and "text" in item:
                partes.append(str(item["text"]))
        texto = "".join(partes)
        if texto:
            return texto

    raise RespostaAgenteInvalida("O modelo não retornou conteúdo textual.")


# Mensagens do turno mantidas no checkpoint (~3 por turno: 21 ≈ 7 turnos). Sem poda o histórico
# cresce sem fim e todo turno o relê inteiro pro contexto do LLM (custo em token).
MAX_MENSAGENS = settings.llm.max_historico_mensagens


def podar_historico(mensagens: Sequence[AnyMessage]) -> list[RemoveMessage]:
    """
    Deltas que apagam as mensagens além de `MAX_MENSAGENS` (vazio quando ainda cabe). Podar por
    contagem só é seguro porque `messages` guarda apenas Human/AI de texto; um `ToolMessage`
    ali poderia separar um tool_call da sua resposta. O corte avança até a próxima pergunta do
    usuário, pra o histórico nunca começar com uma resposta sem a pergunta que a originou.
    """

    if any(isinstance(m, ToolMessage) for m in mensagens):
        logger.warning("ToolMessage no estado — poda desativada para não separar tool_call/resposta.")
        return []

    corte = len(mensagens) - MAX_MENSAGENS
    if corte <= 0:
        return []

    while corte < len(mensagens) and not isinstance(mensagens[corte], HumanMessage):
        corte += 1

    # Sem pergunta depois do ponto de corte, preserva o histórico em vez de esvaziá-lo.
    if corte == len(mensagens):
        return []

    return [RemoveMessage(id=msg.id) for msg in mensagens[:corte] if msg.id]


def revisao_do_juiz(estado: Estado) -> str | None:
    """O pedido de revisão que o Juiz deixou no estado quando reprovou a tentativa anterior."""

    if feedback := estado.get("feedback_juiz"):
        return f"[REVISÃO SOLICITADA PELO JUIZ] {feedback}"
    return None


def mensagens_do_turno(estado: Estado) -> list[AnyMessage]:
    mensagens = list(estado["messages"])

    if revisao := revisao_do_juiz(estado):
        mensagens.append(HumanMessage(content=revisao))

    return mensagens


async def responder(
    app: Runnable[Any, Any], mensagens: Sequence[AnyMessage], contexto: ContextoPrompt | None = None
) -> str:
    """Roda um agente compilado e devolve o texto da última mensagem que ele produziu."""

    saida = await app.ainvoke({"messages": list(mensagens)}, context=contexto)

    return _texto(saida["messages"][-1].content)


async def perguntar(llm: BaseChatModel, entrada: str | Sequence[AnyMessage]) -> str:
    """Roda um LLM cru e devolve o texto. Aceita prompt formatado ou lista de mensagens."""

    resposta = await llm.ainvoke(entrada if isinstance(entrada, str) else list(entrada))

    return _texto(resposta.content)


__all__ = [
    "MAX_MENSAGENS",
    "RespostaAgenteInvalida",
    "mensagens_do_turno",
    "perguntar",
    "podar_historico",
    "responder",
    "revisao_do_juiz",
]
