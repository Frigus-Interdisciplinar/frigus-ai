from frigus_ai.evals.metrics import medir_node
from frigus_ai.graph.agents import compras_app
from frigus_ai.graph.names import COMPRAS
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.state import EspecialistaUpdate, Estado


@medir_node(COMPRAS)
async def no_compras(estado: Estado) -> EspecialistaUpdate:
    resposta = await responder(compras_app, mensagens_do_turno(estado))

    return EspecialistaUpdate(
        agentes_chamados=[COMPRAS],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_compras"]
