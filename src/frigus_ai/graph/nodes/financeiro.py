from frigus_ai.evals.metrics import medir_node
from frigus_ai.graph.agents import financeiro_app
from frigus_ai.graph.names import FINANCEIRO
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.state import EspecialistaUpdate, Estado


@medir_node(FINANCEIRO)
async def no_financeiro(estado: Estado) -> EspecialistaUpdate:
    resposta = await responder(financeiro_app, mensagens_do_turno(estado))

    return EspecialistaUpdate(
        agentes_chamados=[FINANCEIRO],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_financeiro"]
