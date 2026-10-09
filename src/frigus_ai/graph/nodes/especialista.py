from collections.abc import Callable
from functools import wraps

from langchain_core.runnables import Runnable
from langgraph.runtime import Runtime

from frigus_ai.graph.names import NodeLiteral
from frigus_ai.graph.nodes.contexto import mensagens_do_turno, responder
from frigus_ai.graph.state import (
    AsyncNodeComContexto,
    ConteudoEspecialista,
    ContextoPrompt,
    EspecialistaUpdate,
    Estado,
    RouteLiteral,
)
from frigus_ai.telemetry import medir_node


def especialista(
    nome: NodeLiteral, rota: RouteLiteral | None = None
) -> Callable[
    [AsyncNodeComContexto[str | ConteudoEspecialista]], AsyncNodeComContexto[EspecialistaUpdate]
]:
    """
    Nó de especialista: a função devolve só o texto (resposta e dados iguais) ou um
    `ConteudoEspecialista` (quando diferem); o decorator monta o `EspecialistaUpdate` e aplica
    `medir_node`. Especialista nunca publica em `messages` — a resposta final é a do guardrail de
    saída. O nome do parâmetro `runtime` é o que o LangGraph usa pra injetá-lo: mantenha, mesmo
    que a função não o use.
    """

    def decorar(
        func: AsyncNodeComContexto[str | ConteudoEspecialista],
    ) -> AsyncNodeComContexto[EspecialistaUpdate]:
        @wraps(func)
        async def executar(estado: Estado, runtime: Runtime[ContextoPrompt]) -> EspecialistaUpdate:
            conteudo = await func(estado, runtime)

            if isinstance(conteudo, str):
                conteudo = ConteudoEspecialista(resposta=conteudo, dados=conteudo)

            update = EspecialistaUpdate(
                agentes_chamados=[nome],
                resposta_especialista=conteudo["resposta"],
                dados_especialista=conteudo["dados"],
            )
            if rota is not None:
                update["rota"] = rota

            return update

        return medir_node(nome)(executar)

    return decorar


def especialista_com_agente(
    nome: NodeLiteral, agente: Runnable
) -> AsyncNodeComContexto[EspecialistaUpdate]:
    """Nó de especialista que só pergunta ao agente (LLM + tools) com o histórico do turno."""

    @especialista(nome)
    async def no(estado: Estado, runtime: Runtime[ContextoPrompt]) -> str:
        return await responder(agente, mensagens_do_turno(estado), runtime.context)

    return no


__all__ = ["especialista", "especialista_com_agente"]
