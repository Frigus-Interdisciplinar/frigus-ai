from typing import Final

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from frigus_ai.graph.agents import orquestrador_app
from frigus_ai.graph.names import A2A_ASSESSOR, FAQ, ORQUESTRADOR, RECEITAS, NodeLiteral
from frigus_ai.graph.nodes.contexto import responder, revisao_do_juiz
from frigus_ai.graph.state import (
    ContextoPrompt,
    Estado,
    OrquestradorUpdate,
    ResultadoEspecialista,
)
from frigus_ai.telemetry import medir_node

# Já respondem em linguagem natural: sozinhos, passam direto (sem uma chamada de LLM só pra
# reescrever o que já está pronto). Os demais devolvem JSON e precisam ser formatados.
_RESPONDEM_EM_TEXTO: Final[frozenset[NodeLiteral]] = frozenset({RECEITAS, FAQ, A2A_ASSESSOR})


def _nome(resultado: ResultadoEspecialista) -> str:
    return resultado["agente"].removesuffix("_node")


def _dados_para_o_juiz(resultados: list[ResultadoEspecialista]) -> str:
    """O que o Juiz confere: os dados de cada especialista; quem estava indisponível entra só com
    o aviso, pra o Juiz não reprovar a resposta por falta de dado que nunca existiu."""

    return "\n\n".join(
        f"{_nome(r)}:\n{r['dados']}" if r["dados"] else f"{_nome(r)} — indisponível:\n{r['resposta']}"
        for r in resultados
    )


@medir_node(ORQUESTRADOR)
async def no_orquestrador(estado: Estado, runtime: Runtime[ContextoPrompt]) -> OrquestradorUpdate:
    # Ordem estável: especialistas em paralelo terminam em ordem qualquer.
    resultados = sorted(estado["dados_especialistas"], key=lambda r: r["agente"])
    revisao = revisao_do_juiz(estado)

    # Na retentativa o Juiz mandou reescrever, então o LLM roda mesmo com um especialista só.
    if len(resultados) == 1 and resultados[0]["agente"] in _RESPONDEM_EM_TEXTO and not revisao:
        unico = resultados[0]
        return OrquestradorUpdate(
            resposta_especialista=unico["resposta"],
            dados_especialista=unico["dados"],
        )

    respostas = "\n\n".join(f"{_nome(r)}:\n{r['resposta']}" for r in resultados)
    pedido = (
        f"Pedido original:\n{estado['pergunta_original']}\n\n"
        f"Resultados dos especialistas:\n{respostas}"
    )
    if revisao:
        pedido += f"\n\n{revisao}"

    resposta = await responder(orquestrador_app, [HumanMessage(content=pedido)], runtime.context)

    return OrquestradorUpdate(
        resposta_especialista=resposta,
        dados_especialista=_dados_para_o_juiz(resultados),
    )


__all__ = ["no_orquestrador"]
