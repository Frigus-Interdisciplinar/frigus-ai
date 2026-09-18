"""
Glue entre os nós do grafo e os modelos (agentes compilados de `graph/agents.py` ou LLMs crus
de `graph/llm.py`).

Os dois formatos de saída não são iguais: um agente devolve `{"messages": [...]}` e o texto está
na última mensagem; um LLM cru devolve uma `AIMessage` só. Daí `responder` e `perguntar`. Antes,
cada nó fazia `["messages"][-1].content` ou `.content` na mão, e nenhum checava se o conteúdo era
mesmo texto — com resposta multimodal, o `str` vazava pro resto do grafo como lista de blocos.

`mensagens_do_turno` monta a entrada do especialista: histórico (ou só a pergunta que o
roteador encaminhou) mais o feedback do Juiz, quando ele reprovou a tentativa anterior —
esse append estava copiado em cinco nodes.
"""

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import Runnable

from frigus_ai.graph.state import Estado


class RespostaAgenteInvalida(RuntimeError):
    pass


def _texto(conteudo: Any) -> str:
    if not isinstance(conteudo, str):
        raise RespostaAgenteInvalida("O modelo não retornou conteúdo textual.")

    return conteudo


# Quantas mensagens do turno ficam no checkpoint. O canal `messages` cresce ~3 por turno
# (pergunta do usuário + resposta do especialista/orquestrador + resposta do guardrail de
# saída), então 21 ≈ 7 turnos. Sem poda, `thread_id` de vida longa cresce para sempre: o
# documento no Mongo incha e, pior, TODO turno relê o histórico inteiro pra dentro do
# contexto do LLM — custo em token cresce junto, não só memória.
MAX_MENSAGENS = 21


def podar_historico(mensagens: Sequence[AnyMessage]) -> list[RemoveMessage]:
    """
    Deltas que apagam as mensagens mais antigas além de `MAX_MENSAGENS`, para o reducer
    `add_messages` aplicar. Lista vazia quando ainda cabe.

    Podar por contagem só é seguro porque o canal `messages` guarda apenas Human/AI de
    texto: as tools rodam dentro do sub-grafo de cada agente e os nós publicam somente a
    mensagem final. Se algum dia um `ToolMessage` entrar no estado, cortar por índice pode
    separar um tool_call da sua resposta e quebrar a próxima chamada do modelo.
    """

    excedente = len(mensagens) - MAX_MENSAGENS
    if excedente <= 0:
        return []

    return [RemoveMessage(id=msg.id) for msg in mensagens[:excedente] if msg.id]


def mensagens_do_turno(estado: Estado, apenas_pergunta: bool = False) -> list[AnyMessage]:
    """
    `apenas_pergunta=True` para os nós que respondem em linguagem natural a partir da
    pergunta isolada (FAQ, Receitas); os demais recebem o histórico inteiro do turno.
    """

    if apenas_pergunta:
        mensagens: list[AnyMessage] = [HumanMessage(content=estado.get("pergunta_original", ""))]
    else:
        mensagens = list(estado["messages"])

    feedback = estado.get("feedback_juiz")
    if feedback:
        mensagens.append(
            HumanMessage(content=f"[REVISÃO SOLICITADA PELO JUIZ] {feedback}")
        )

    return mensagens


async def responder(app: Runnable[Any, Any], mensagens: Sequence[AnyMessage]) -> str:
    """Roda um agente compilado e devolve o texto da última mensagem que ele produziu."""

    saida = await app.ainvoke({"messages": list(mensagens)})

    return _texto(saida["messages"][-1].content)


async def perguntar(llm: BaseChatModel, entrada: str | Sequence[AnyMessage]) -> str:
    """
    Roda um LLM cru (sem tools nem agente em volta) e devolve o texto da resposta.

    Aceita prompt já formatado (guardrails) ou lista de mensagens (Juiz).
    """

    resposta = await llm.ainvoke(entrada if isinstance(entrada, str) else list(entrada))

    return _texto(resposta.content)


__all__ = [
    "MAX_MENSAGENS",
    "RespostaAgenteInvalida",
    "mensagens_do_turno",
    "perguntar",
    "podar_historico",
    "responder",
]
