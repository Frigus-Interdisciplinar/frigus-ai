from frigus_ai.agents.nodes.names import Node
from frigus_ai.graph.agents import orquestrador_app
from frigus_ai.graph.state import Estado


def no_orquestrador(estado: Estado) -> dict:

    mensagens = list(estado["messages"]) + [
        {"role": "human", "content": estado["resposta_especialista"]}
    ]

    saida = orquestrador_app.invoke({"messages": mensagens})

    return {
        "agentes_chamados":      [Node.ORQUESTRADOR],
        "messages":              [{"role": "assistant", "content": saida["messages"][-1].content}],
        "resposta_especialista": saida["messages"][-1].content,
    }


__all__ = ["no_orquestrador"]
