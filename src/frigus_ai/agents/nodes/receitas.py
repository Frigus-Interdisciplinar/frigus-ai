from frigus_ai.agents.nodes.names import Node
from frigus_ai.graph.agents import receitas_app
from frigus_ai.graph.state import Estado


async def no_receitas(estado: Estado) -> dict:

    mensagens = [{"role": "human", "content": estado["pergunta_original"]}]

    feedback = estado.get("feedback_juiz")
    if feedback:
        mensagens.append({"role": "human", "content": f"[REVISÃO SOLICITADA PELO JUIZ] {feedback}"})

    saida = await receitas_app.ainvoke({"messages": mensagens})
    resposta = saida["messages"][-1].content

    return {
        "agentes_chamados":      [Node.RECEITAS],
        "messages":              [{"role": "assistant", "content": resposta}],
        "resposta_especialista": resposta,
        "dados_especialista":    resposta,
    }


__all__ = ["no_receitas"]
