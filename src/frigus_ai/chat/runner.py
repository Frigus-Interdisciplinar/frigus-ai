from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.graph.builder import fluxo_agentes
from frigus_ai.tools.postgres.context import session_context


def _texto_assistente(msg) -> str | None:
    """
    Os nós devolvem a mensagem final ora como `AIMessage` (estado consolidado do
    `ainvoke`), ora como dict cru `{"role": "assistant", ...}` (delta do `astream`,
    antes do reducer). As duas formas passam por aqui.
    """

    if isinstance(msg, AIMessage):
        return msg.content
    if isinstance(msg, dict) and msg.get("role") == "assistant":
        return msg.get("content")
    return None


def _extrair_resposta(estado: dict) -> str | None:
    for msg in estado.get("messages", [])[::-1]:
        if (texto := _texto_assistente(msg)) is not None:
            return texto
    return None


def _estado_inicial(conteudo: str, stock_id: int | None, perfil_usuario: str) -> dict:
    return {
        "messages":         [HumanMessage(content=conteudo)],
        "agentes_chamados": [],
        "perfil_usuario":   perfil_usuario,
        "stock_id":         stock_id,
        "tentativas_juiz":  0,
    }


def _config(session_id: str, user_id: int) -> dict:
    return {
        "configurable": {"thread_id": session_id},
        "tags": ["chat"],
        "metadata": {"user_id": user_id, "session_id": session_id},
    }


async def executar(
    conteudo: str,
    session_id: str,
    user_id: int,
    stock_id: int | None,
    perfil_usuario: str,
) -> str | None:
    # stock_id/user_id ficam disponíveis via contextvars para as tools de
    # Postgres (tools/postgres/context.py) durante toda a invocação do grafo.
    with session_context(user_id=user_id, stock_id=stock_id):
        estado_final = await fluxo_agentes().ainvoke(
            _estado_inicial(conteudo, stock_id, perfil_usuario),
            config=_config(session_id, user_id),
        )

    return _extrair_resposta(estado_final)


async def executar_stream(
    conteudo: str,
    session_id: str,
    user_id: int,
    stock_id: int | None,
    perfil_usuario: str,
) -> AsyncIterator[tuple[str, str]]:
    """
    Emite `("no", nome_do_no)` a cada nó concluído e `("resposta", texto)` no fim.

    É progresso por nó, não token a token: quem produz o texto final é o
    `guardrail_saida`, que reescreve a resposta inteira depois que o LLM termina
    (`agents/nodes/guardrail/saida.py`) — não há token final pra streamar antes disso.
    """

    resposta = None

    with session_context(user_id=user_id, stock_id=stock_id):
        async for update in fluxo_agentes().astream(
            _estado_inicial(conteudo, stock_id, perfil_usuario),
            config=_config(session_id, user_id),
            stream_mode="updates",
        ):
            for no, delta in update.items():
                yield "no", no
                resposta = _extrair_resposta(delta or {}) or resposta

    yield "resposta", resposta or "Sem resposta."
