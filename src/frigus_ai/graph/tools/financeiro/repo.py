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
from frigus_ai.repositories import financeiro_repository


def _mes_ou_atual(mes: str | None) -> str:
    return mes or date.today().strftime("%Y-%m")


def _mes_anterior(hoje: date) -> str:
    return (hoje.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


class FinanceiroRepo(ToolSet):
    def gastos_mensais(self, mes: str | None = None) -> dict:
        """
        Retorna o total gasto em compras de produtos (Entradas em stock_movements)
        no mês informado (YYYY-MM). Sem mês informado, usa o mês atual.
        """

        mes_alvo = _mes_ou_atual(mes)
        gastos = financeiro_repository.gastos_por_mes(current_stock_id(), [mes_alvo])
        return Response.ok(mes=mes_alvo, total_gasto=gastos[mes_alvo])

    def comparacao_mensal(self) -> dict:
        """
        Compara o gasto do mês atual com o do mês anterior.
        """

        hoje = date.today()
        mes_atual = hoje.strftime("%Y-%m")
        mes_anterior = _mes_anterior(hoje)

        gastos = financeiro_repository.gastos_por_mes(current_stock_id(), [mes_atual, mes_anterior])
        gasto_atual = gastos[mes_atual]
        gasto_anterior = gastos[mes_anterior]
        variacao = gasto_atual - gasto_anterior

        # Sem base de comparação (mês anterior zerado) o percentual seria divisão por
        # zero — devolve None e deixa o especialista explicar em texto.
        variacao_pct = round((variacao / gasto_anterior) * 100, 1) if gasto_anterior else None

        return Response.ok(
            mes_atual=mes_atual,
            gasto_mes_atual=gasto_atual,
            mes_anterior=mes_anterior,
            gasto_mes_anterior=gasto_anterior,
            variacao_absoluta=variacao,
            variacao_percentual=variacao_pct,
        )

    def valor_descartado(self, mes: str | None = None) -> dict:
        """
        Retorna o valor estimado dos alimentos descartados (vencidos/estragados)
        no mês informado (YYYY-MM). Sem mês informado, usa o mês atual.
        """

        mes_alvo = _mes_ou_atual(mes)
        total = financeiro_repository.valor_descartado_do_mes(current_stock_id(), mes_alvo)
        return Response.ok(mes=mes_alvo, valor_descartado=total)

    def evolucao_desperdicio(self, meses: int = 6) -> dict:
        """
        Retorna a série histórica (últimos N meses, incluindo o atual) do valor
        descartado por desperdício, para visualizar a tendência ao longo do tempo.
        """

        serie = financeiro_repository.evolucao_desperdicio(current_stock_id(), meses)
        return Response.ok(serie=serie)

    def ranking_desperdicio(self, limit: int = 5) -> dict:
        """
        Retorna os produtos mais descartados por desperdício (quantidade acumulada,
        todo o histórico), do maior pro menor.
        """

        top = ranking.top_desperdicio(current_stock_id(), limit)
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
