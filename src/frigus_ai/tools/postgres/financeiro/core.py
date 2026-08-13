from datetime import date, timedelta

from langchain.tools import tool

from config.decorators import log_tool
from config.logging import get_logger
from frigus_ai.tools.postgres.connection import get_conn
from frigus_ai.tools.postgres.context import current_stock_id
from frigus_ai.tools.postgres.financeiro.schemas import EvolucaoDesperdicioArgs, MesArgs
from frigus_ai.tools.response import Response

logger = get_logger("pg_financeiro")


def _mes_ou_atual(mes: str | None) -> str:
    return mes or date.today().strftime("%Y-%m")


def _gasto_do_mes(cur, stock_id: int, mes: str) -> float:
    cur.execute(
        """
        SELECT COALESCE(SUM(sm.quantity * p.unit_price), 0)
        FROM stock_movements sm
        JOIN stock_products sp ON sp.id = sm.stock_product_id
        JOIN products p ON p.id = sp.product_id
        WHERE sp.stock_id = %s
          AND sm.movement_type = 'Entrada'
          AND to_char(sm.date, 'YYYY-MM') = %s;
        """,
        (stock_id, mes)
    )
    return float(cur.fetchone()[0])


def _valor_descartado_do_mes(cur, stock_id: int, mes: str) -> float:
    cur.execute(
        """
        SELECT COALESCE(SUM(sm.quantity * p.unit_price), 0)
        FROM discard d
        JOIN stock_products sp ON sp.id = d.stock_product_id
        JOIN products p ON p.id = sp.product_id
        JOIN stock_movements sm ON sm.stock_product_id = d.stock_product_id
                                AND sm.date = d.date
                                AND sm.movement_type = 'Saída'
        WHERE sp.stock_id = %s
          AND to_char(d.date, 'YYYY-MM') = %s;
        """,
        (stock_id, mes)
    )
    return float(cur.fetchone()[0])


@tool("gastos_mensais", args_schema=MesArgs)
@log_tool
def gastos_mensais(mes: str | None = None) -> dict:
    """
    Retorna o total gasto em compras de produtos (Entradas em stock_movements)
    no mês informado (YYYY-MM). Sem mês informado, usa o mês atual.
    """

    stock_id = current_stock_id()
    mes_alvo = _mes_ou_atual(mes)

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                total = _gasto_do_mes(cur, stock_id, mes_alvo)
                logger.info("QUERY OK | gastos_mensais | mes=%s total=%.2f", mes_alvo, total)
                return Response.ok(mes=mes_alvo, total_gasto=total)
            except Exception as e:
                logger.error("QUERY ERRO | gastos_mensais | %s", e)
                return Response.error(e)


@tool("comparacao_mensal")
@log_tool
def comparacao_mensal() -> dict:
    """
    Compara o gasto do mês atual com o do mês anterior.
    """

    stock_id = current_stock_id()
    hoje = date.today()
    mes_atual = hoje.strftime("%Y-%m")

    mes_anterior_data = hoje.replace(day=1) - timedelta(days=1)
    mes_anterior = mes_anterior_data.strftime("%Y-%m")

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                gasto_atual = _gasto_do_mes(cur, stock_id, mes_atual)
                gasto_anterior = _gasto_do_mes(cur, stock_id, mes_anterior)
                variacao = gasto_atual - gasto_anterior
                variacao_pct = round((variacao / gasto_anterior) * 100, 1) if gasto_anterior else None

                logger.info(
                    "QUERY OK | comparacao_mensal | atual=%.2f anterior=%.2f",
                    gasto_atual, gasto_anterior
                )

                return Response.ok(
                    mes_atual=mes_atual,
                    gasto_mes_atual=gasto_atual,
                    mes_anterior=mes_anterior,
                    gasto_mes_anterior=gasto_anterior,
                    variacao_absoluta=variacao,
                    variacao_percentual=variacao_pct,
                )
            except Exception as e:
                logger.error("QUERY ERRO | comparacao_mensal | %s", e)
                return Response.error(e)


@tool("valor_descartado", args_schema=MesArgs)
@log_tool
def valor_descartado(mes: str | None = None) -> dict:
    """
    Retorna o valor estimado dos alimentos descartados (vencidos/estragados)
    no mês informado (YYYY-MM). Sem mês informado, usa o mês atual.
    """

    stock_id = current_stock_id()
    mes_alvo = _mes_ou_atual(mes)

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                total = _valor_descartado_do_mes(cur, stock_id, mes_alvo)
                logger.info("QUERY OK | valor_descartado | mes=%s total=%.2f", mes_alvo, total)
                return Response.ok(mes=mes_alvo, valor_descartado=total)
            except Exception as e:
                logger.error("QUERY ERRO | valor_descartado | %s", e)
                return Response.error(e)


@tool("evolucao_desperdicio", args_schema=EvolucaoDesperdicioArgs)
@log_tool
def evolucao_desperdicio(meses: int = 6) -> dict:
    """
    Retorna a série histórica (últimos N meses, incluindo o atual) do valor
    descartado por desperdício, para visualizar a tendência ao longo do tempo.
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT to_char(d.date, 'YYYY-MM') AS mes,
                           COALESCE(SUM(sm.quantity * p.unit_price), 0) AS valor
                    FROM discard d
                    JOIN stock_products sp ON sp.id = d.stock_product_id
                    JOIN products p ON p.id = sp.product_id
                    JOIN stock_movements sm ON sm.stock_product_id = d.stock_product_id
                                            AND sm.date = d.date
                                            AND sm.movement_type = 'Saída'
                    WHERE sp.stock_id = %s
                      AND d.date >= (CURRENT_DATE - (%s || ' months')::interval)
                    GROUP BY mes
                    ORDER BY mes ASC;
                    """,
                    (stock_id, meses)
                )
                serie = [{"mes": row[0], "valor_descartado": float(row[1])} for row in cur.fetchall()]

                logger.info("QUERY OK | evolucao_desperdicio | meses=%s pontos=%s", meses, len(serie))

                return Response.ok(serie=serie)
            except Exception as e:
                logger.error("QUERY ERRO | evolucao_desperdicio | %s", e)
                return Response.error(e)


__all__ = [
    "comparacao_mensal",
    "evolucao_desperdicio",
    "gastos_mensais",
    "valor_descartado",
]
