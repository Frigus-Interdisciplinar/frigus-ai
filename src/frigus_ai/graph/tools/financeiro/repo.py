from datetime import date, timedelta

from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.financeiro.schemas import (
    EvolucaoDesperdicioArgs,
    MesArgs,
    RankingDesperdicioArgs,
)
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.postgres.context import current_stock_id
from frigus_ai.infra.redis import ranking
from frigus_ai.logging import Logging
from frigus_ai.repositories import financeiro_repository

logger = Logging.get_logger("pg_financeiro")


def _mes_ou_atual(mes: str | None) -> str:
    return mes or date.today().strftime("%Y-%m")


def _mes_anterior(hoje: date) -> str:
    return (hoje.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


class FinanceiroRepo(ToolSet):
    @Logging.log_tool
    def gastos_mensais(self, mes: str | None = None) -> dict:
        """
        Retorna o total gasto em compras de produtos (Entradas em stock_movements)
        no mês informado (YYYY-MM). Sem mês informado, usa o mês atual.
        """

        mes_alvo = _mes_ou_atual(mes)

        try:
            gastos = financeiro_repository.gastos_por_mes(current_stock_id(), [mes_alvo])
        except Exception as e:
            logger.error("QUERY ERRO | gastos_mensais | %s", e)
            return Response.error(e)

        total = gastos[mes_alvo]
        logger.info("QUERY OK | gastos_mensais | mes=%s total=%.2f", mes_alvo, total)
        return Response.ok(mes=mes_alvo, total_gasto=total)

    @Logging.log_tool
    def comparacao_mensal(self) -> dict:
        """
        Compara o gasto do mês atual com o do mês anterior.
        """

        hoje = date.today()
        mes_atual = hoje.strftime("%Y-%m")
        mes_anterior = _mes_anterior(hoje)

        try:
            gastos = financeiro_repository.gastos_por_mes(
                current_stock_id(), [mes_atual, mes_anterior]
            )
        except Exception as e:
            logger.error("QUERY ERRO | comparacao_mensal | %s", e)
            return Response.error(e)

        gasto_atual = gastos[mes_atual]
        gasto_anterior = gastos[mes_anterior]
        variacao = gasto_atual - gasto_anterior

        # Sem base de comparação (mês anterior zerado) o percentual seria divisão por
        # zero — devolve None e deixa o especialista explicar em texto.
        variacao_pct = round((variacao / gasto_anterior) * 100, 1) if gasto_anterior else None

        logger.info(
            "QUERY OK | comparacao_mensal | atual=%.2f anterior=%.2f", gasto_atual, gasto_anterior
        )

        return Response.ok(
            mes_atual=mes_atual,
            gasto_mes_atual=gasto_atual,
            mes_anterior=mes_anterior,
            gasto_mes_anterior=gasto_anterior,
            variacao_absoluta=variacao,
            variacao_percentual=variacao_pct,
        )

    @Logging.log_tool
    def valor_descartado(self, mes: str | None = None) -> dict:
        """
        Retorna o valor estimado dos alimentos descartados (vencidos/estragados)
        no mês informado (YYYY-MM). Sem mês informado, usa o mês atual.
        """

        mes_alvo = _mes_ou_atual(mes)

        try:
            total = financeiro_repository.valor_descartado_do_mes(current_stock_id(), mes_alvo)
        except Exception as e:
            logger.error("QUERY ERRO | valor_descartado | %s", e)
            return Response.error(e)

        logger.info("QUERY OK | valor_descartado | mes=%s total=%.2f", mes_alvo, total)
        return Response.ok(mes=mes_alvo, valor_descartado=total)

    @Logging.log_tool
    def evolucao_desperdicio(self, meses: int = 6) -> dict:
        """
        Retorna a série histórica (últimos N meses, incluindo o atual) do valor
        descartado por desperdício, para visualizar a tendência ao longo do tempo.
        """

        try:
            serie = financeiro_repository.evolucao_desperdicio(current_stock_id(), meses)
        except Exception as e:
            logger.error("QUERY ERRO | evolucao_desperdicio | %s", e)
            return Response.error(e)

        logger.info("QUERY OK | evolucao_desperdicio | meses=%s pontos=%s", meses, len(serie))
        return Response.ok(serie=serie)

    @Logging.log_tool
    def ranking_desperdicio(self, limit: int = 5) -> dict:
        """
        Retorna os produtos mais descartados por desperdício (quantidade acumulada,
        todo o histórico), do maior pro menor.
        """

        try:
            top = ranking.top_desperdicio(current_stock_id(), limit)
        except Exception as e:
            logger.error("QUERY ERRO | ranking_desperdicio | %s", e)
            return Response.error(e)

        logger.info("QUERY OK | ranking_desperdicio | total=%s", len(top))
        return Response.ok(ranking=[{"product_name": p, "quantidade": q} for p, q in top])

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                self.gastos_mensais, name="gastos_mensais", args_schema=MesArgs
            ),
            StructuredTool.from_function(self.comparacao_mensal, name="comparacao_mensal"),
            StructuredTool.from_function(
                self.valor_descartado, name="valor_descartado", args_schema=MesArgs
            ),
            StructuredTool.from_function(
                self.evolucao_desperdicio,
                name="evolucao_desperdicio",
                args_schema=EvolucaoDesperdicioArgs,
            ),
            StructuredTool.from_function(
                self.ranking_desperdicio,
                name="ranking_desperdicio",
                args_schema=RankingDesperdicioArgs,
            ),
        ]


__all__ = ["FinanceiroRepo"]
