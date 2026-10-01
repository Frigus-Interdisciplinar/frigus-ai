from frigus_ai.graph.agents import estoque_app
from frigus_ai.graph.names import ESTOQUE
from frigus_ai.graph.nodes.contexto import (
    contexto_do_estado,
    mensagens_do_turno,
    responder,
)
from frigus_ai.graph.state import EspecialistaUpdate, Estado
from frigus_ai.observability import medir_node


@medir_node(ESTOQUE)
async def no_estoque(estado: Estado) -> EspecialistaUpdate:
    resposta = await responder(estoque_app, mensagens_do_turno(estado), contexto_do_estado(estado))

    return EspecialistaUpdate(
        agentes_chamados=[ESTOQUE],
        resposta_especialista=resposta,
        dados_especialista=resposta,
    )


__all__ = ["no_estoque"]
