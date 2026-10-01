from frigus_ai.graph.agents import financeiro_app
from frigus_ai.graph.names import FINANCEIRO
from frigus_ai.graph.nodes.contexto import (
    contexto_do_estado,
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import EspecialistaUpdate, Estado
from frigus_ai.observability import medir_node


@medir_node(FINANCEIRO)
async def no_financeiro(estado: Estado) -> EspecialistaUpdate:
    resposta = await responder(financeiro_app, mensagens_do_turno(estado), contexto_do_estado(estado))

    return EspecialistaUpdate(
        agentes_chamados=[FINANCEIRO],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_financeiro"]
