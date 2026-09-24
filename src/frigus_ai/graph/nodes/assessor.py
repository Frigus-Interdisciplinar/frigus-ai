"""
Planejamento financeiro da alimentação delegado ao assessor-ai via A2A: o Frigus manda os
números que só ele tem (gasto com comida, valor descartado, o que mais se desperdiça) e o
Assessor devolve a análise — orçamento de mercado, plano de economia.

A direção é essa, e não o Frigus consultar a conta do usuário no Assessor (saldo, registrar
gasto), porque a `ASSESSOR_API_KEY` é uma só: como proxy de conta, todo usuário do Frigus
veria a mesma conta. Mandando os dados junto, a key vira só uma conta de serviço.

Consultar os números em si ("quanto gastei?") continua no `financeiro_node` — a separação é
do roteador (`router.md`). Não é agente local: sem LLM nem tool aqui.
"""

import asyncio
from datetime import date, timedelta

from langchain_core.messages import AIMessage
from langgraph.config import get_config

from frigus_ai.exceptions import AssessorIndisponivel
from frigus_ai.graph.names import A2A_ASSESSOR
from frigus_ai.graph.state import AssessorUpdate, Estado
from frigus_ai.infra.assessor import client as assessor
from frigus_ai.infra.postgres.context import current_stock_id
from frigus_ai.infra.redis import ranking
from frigus_ai.logging import Logging
from frigus_ai.observability.metrics import medir_node
from frigus_ai.repositories import financeiro_repository

logger = Logging.get_logger(__name__)

INDISPONIVEL = (
    "Não consegui falar com o Assessor financeiro agora, então fico devendo o plano de "
    "economia. Tente de novo em alguns minutos — quanto você gastou ou desperdiçou com "
    "comida eu consigo responder por aqui."
)


def _session_id() -> str:
    # thread_id do checkpointer = session_id do chat (ver runner._config).
    return get_config().get("configurable", {}).get("thread_id", "")


def _reais(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def _contexto_financeiro() -> str:
    """Números de alimentação do estoque do turno, em texto pro Assessor. Síncrono (Postgres
    e Redis são clients sync) — roda via `to_thread`, que leva junto o `session_context`."""

    stock_id = current_stock_id()
    hoje = date.today()
    mes = hoje.strftime("%Y-%m")
    anterior = (hoje.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    gastos = financeiro_repository.gastos_por_mes(stock_id, [mes, anterior])
    descartado = financeiro_repository.valor_descartado_do_mes(stock_id, mes)
    top = ranking.top_desperdicio(stock_id, 5)

    linhas = [
        (
            f"- Gasto com compras de alimentos em {mes}: {_reais(gastos[mes])} "
            f"(em {anterior}: {_reais(gastos[anterior])})"
        ),
        f"- Valor de alimentos jogados fora em {mes}: {_reais(descartado)}",
    ]
    if top:
        itens = ", ".join(f"{produto} ({quantidade:g}x)" for produto, quantidade in top)
        linhas.append(f"- Produtos mais descartados: {itens}")

    return "\n".join(linhas)


def _mensagem(pergunta: str, contexto: str) -> str:
    if not contexto:
        return pergunta

    return (
        f"{pergunta}\n\n"
        "Dados de alimentação deste usuário, enviados pelo Frigus (app de gestão de alimentos):\n"
        f"{contexto}\n\n"
        "Baseie a análise nesses dados. Não use saldo, transações ou perfil da conta que está "
        "chamando: ela é uma conta de serviço do Frigus, não a do usuário."
    )


@medir_node(A2A_ASSESSOR)
async def no_assessor(estado: Estado) -> AssessorUpdate:
    pergunta = estado.get("pergunta_original", "")
    if feedback := estado.get("feedback_juiz"):
        pergunta += f"\n\n[REVISÃO SOLICITADA] {feedback}"

    try:
        contexto = await asyncio.to_thread(_contexto_financeiro)
    except Exception as e:  # sem estoque na sessão, Postgres/Redis fora: pergunta sem dados
        logger.warning(f"Sem dados financeiros pro Assessor, perguntando sem contexto: {e}")
        contexto = ""

    try:
        resposta = await assessor.perguntar(_mensagem(pergunta, contexto), _session_id())
    except AssessorIndisponivel as e:
        logger.warning(f"Assessor indisponível: {e}")

        return AssessorUpdate(
            agentes_chamados=[A2A_ASSESSOR],
            messages=[AIMessage(content=INDISPONIVEL)],
            resposta_especialista=INDISPONIVEL,
            dados_especialista="",
        )

    return AssessorUpdate(
        agentes_chamados=[A2A_ASSESSOR],
        messages=[AIMessage(content=resposta)],
        resposta_especialista=resposta,
        dados_especialista=f"{contexto}\n\n{resposta}" if contexto else resposta,
    )


__all__ = ["INDISPONIVEL", "no_assessor"]
