from frigus_ai.agents.nodes.names import NodeName
from frigus_ai.graph.agents import financeiro_app
from frigus_ai.graph.state import Estado


def no_financeiro(estado: Estado) -> dict:

    mensagens = list(estado["messages"])

    feedback = estado.get("feedback_juiz")
    if feedback:
        mensagens = mensagens + [{"role": "human", "content": f"[REVISÃO SOLICITADA PELO JUIZ] {feedback}"}]

    saida = financeiro_app.invoke({"messages": mensagens})
    resposta = saida["messages"][-1].content

    return {
        "agentes_chamados":      [NodeName.FINANCEIRO],
        "resposta_especialista": resposta,
        "dados_especialista":    resposta,
    }


__all__ = ["no_financeiro"]
