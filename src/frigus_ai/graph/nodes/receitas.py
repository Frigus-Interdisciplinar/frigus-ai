from langchain_core.messages import AIMessage

from frigus_ai.evals.metrics import medir_node
from frigus_ai.graph.agents import receitas_app
from frigus_ai.graph.names import RECEITAS
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.state import Estado, FaqUpdate


@medir_node(RECEITAS)
async def no_receitas(estado: Estado) -> FaqUpdate:
    resposta = await responder(receitas_app, mensagens_do_turno(estado, apenas_pergunta=True))

    return FaqUpdate(
        agentes_chamados=[RECEITAS],
        messages=[AIMessage(content=resposta)],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_receitas"]
