from langgraph.runtime import Runtime

from frigus_ai.graph.agents import financeiro_app
from frigus_ai.graph.names import FINANCEIRO
from frigus_ai.graph.nodes.contexto import (
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import ContextoPrompt, EspecialistaUpdate, Estado
from frigus_ai.telemetry import medir_node


@medir_node(FINANCEIRO)
async def no_financeiro(estado: Estado, runtime: Runtime[ContextoPrompt]) -> EspecialistaUpdate:
    resposta = await responder(financeiro_app, mensagens_do_turno(estado), runtime.context)

    return EspecialistaUpdate(
        agentes_chamados=[FINANCEIRO],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_financeiro"]
