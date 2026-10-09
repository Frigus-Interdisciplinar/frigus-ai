from langgraph.runtime import Runtime

from frigus_ai.graph.agents import estoque_app
from frigus_ai.graph.names import ESTOQUE
from frigus_ai.graph.nodes.contexto import (
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import ContextoPrompt, EspecialistaUpdate, Estado
from frigus_ai.telemetry import medir_node


@medir_node(ESTOQUE)
async def no_estoque(estado: Estado, runtime: Runtime[ContextoPrompt]) -> EspecialistaUpdate:
    resposta = await responder(estoque_app, mensagens_do_turno(estado), runtime.context)

    return EspecialistaUpdate(
        agentes_chamados=[ESTOQUE],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_estoque"]
