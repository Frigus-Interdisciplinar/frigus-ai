from frigus_ai.agents.nodes.names import NodeName
from frigus_ai.graph.agents import faq_app
from frigus_ai.graph.state import Estado


def no_faq(estado: Estado) -> dict:

    mensagens = [{"role": "human", "content": estado["pergunta_original"]}]

    feedback = estado.get("feedback_juiz")
    if feedback:
        mensagens.append({"role": "human", "content": f"[REVISÃO SOLICITADA PELO JUIZ] {feedback}"})

    saida = faq_app.invoke({"messages": mensagens})
    resposta = saida["messages"][-1].content

    return {
        "agentes_chamados":      [NodeName.FAQ],
        "messages":              [{"role": "assistant", "content": resposta}],
        "resposta_especialista": resposta,
        "dados_especialista":    resposta,
    }


__all__ = ["no_faq"]
