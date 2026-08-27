from frigus_ai.agents.nodes.names import Node
from frigus_ai.graph.agents import estoque_app
from frigus_ai.graph.state import Estado


async def no_estoque(estado: Estado) -> dict:

    mensagens = list(estado["messages"])

    feedback = estado.get("feedback_juiz")
    if feedback:
        mensagens = mensagens + [{"role": "human", "content": f"[REVISÃO SOLICITADA PELO JUIZ] {feedback}"}]

    saida = await estoque_app.ainvoke({"messages": mensagens})
    resposta = saida["messages"][-1].content

    return {
        "agentes_chamados":      [Node.ESTOQUE],
        "resposta_especialista": resposta,
        "dados_especialista":    resposta,
    }


__all__ = ["no_estoque"]
