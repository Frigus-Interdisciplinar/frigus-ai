from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.graph.builder import fluxo_agentes
from frigus_ai.tools.postgres.context import session_context


def _extrair_resposta(estado_final: dict) -> str | None:
    for msg in estado_final["messages"][::-1]:
        if isinstance(msg, AIMessage):
            return msg.content
    return None


def executar(
    conteudo: str,
    session_id: str,
    user_id: int,
    stock_id: int | None,
    perfil_usuario: str,
) -> str | None:
    estado_inicial = {
        "messages":         [HumanMessage(content=conteudo)],
        "agentes_chamados": [],
        "perfil_usuario":   perfil_usuario,
        "stock_id":         stock_id,
        "tentativas_juiz":  0,
    }

    # stock_id/user_id ficam disponíveis via contextvars para as tools de
    # Postgres (tools/postgres/context.py) durante toda a invocação do grafo.
    with session_context(user_id=user_id, stock_id=stock_id):
        estado_final = fluxo_agentes.invoke(
            estado_inicial,
            config={"configurable": {"thread_id": session_id}},
        )

    return _extrair_resposta(estado_final)
