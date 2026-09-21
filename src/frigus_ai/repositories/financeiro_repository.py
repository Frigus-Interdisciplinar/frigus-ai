"""
Persistência crua do domínio financeiro: quanto entrou (compras) e quanto foi descartado
por desperdício, por mês. Sem decisão de negócio nem tradução pra `Response` — isso fica
em `graph/tools/financeiro/repo.py` (a tool que o LLM chama).

O financeiro não tem tabela própria: ele deriva tudo de `stock_movements` (entradas) e
`discard` (saídas por desperdício), sempre multiplicando quantidade por `products.unit_price`.
"""

from collections.abc import Sequence
from datetime import date
from typing import TypedDict

from sqlalchemy import Interval, cast, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from frigus_ai.infra.postgres.connection import PostgresRepo, transacional
from frigus_ai.infra.postgres.models import (
    ENTRADA,
    SAIDA,
    Discard,
    Product,
    StockMovement,
    StockProduct,
)


class PontoDesperdicio(TypedDict):
    mes: str
    valor_descartado: float


def _competencia(coluna: ColumnElement[date | None]) -> ColumnElement[str]:
    """`YYYY-MM` da data — a granularidade de todo relatório financeiro daqui."""

    return func.to_char(coluna, "YYYY-MM")


def _valor() -> ColumnElement[float]:
    """Soma de quantidade * preço unitário, zero quando não há linha nenhuma."""

    return func.coalesce(func.sum(StockMovement.quantity * Product.unit_price), 0)


def _descartes_com_valor():
    """
    `discard` guarda o que foi jogado fora, mas não a quantidade — essa mora na saída
    correspondente em `stock_movements`, casada por (stock_product_id, date). Daí o join
    triplo repetido nas duas consultas de desperdício.
    """

    return (
        select(Discard.date.label("data"), (StockMovement.quantity * Product.unit_price).label("valor"))
        .select_from(Discard)
        .join(StockProduct, StockProduct.id == Discard.stock_product_id)
        .join(Product, Product.id == StockProduct.product_id)
        .join(
            StockMovement,
            (StockMovement.stock_product_id == Discard.stock_product_id)
            & (StockMovement.date == Discard.date)
            & (StockMovement.movement_type == SAIDA),
        )
    )


class _FinanceiroPostgresRepo(PostgresRepo):
    @transacional
    def gastos_por_mes(
        self, s: Session, stock_id: int, meses: Sequence[str]
    ) -> dict[str, float]:
        """
        Total de entradas por competência. Uma query só para todos os meses pedidos;
        mês sem movimento nenhum volta como 0.0 em vez de sumir do resultado.
        """

        mes = _competencia(StockMovement.date)

        stmt = (
            select(mes.label("mes"), _valor())
            .select_from(StockMovement)
            .join(StockProduct, StockProduct.id == StockMovement.stock_product_id)
            .join(Product, Product.id == StockProduct.product_id)
            .where(
                StockProduct.stock_id == stock_id,
                StockMovement.movement_type == ENTRADA,
                mes.in_(list(meses)),
            )
            .group_by(mes)
        )

        encontrados = {competencia: float(total) for competencia, total in s.execute(stmt)}

        return {competencia: encontrados.get(competencia, 0.0) for competencia in meses}

    @transacional
    def valor_descartado_do_mes(self, s: Session, stock_id: int, mes: str) -> float:
        descartes = _descartes_com_valor().where(
            StockProduct.stock_id == stock_id,
            _competencia(Discard.date) == mes,
        ).subquery()

        total = s.scalar(select(func.coalesce(func.sum(descartes.c.valor), 0)))

        return float(total or 0)

    @transacional
    def evolucao_desperdicio(
        self, s: Session, stock_id: int, meses: int
    ) -> list[PontoDesperdicio]:
        """Série do valor descartado nos últimos N meses, do mais antigo pro mais recente."""

        janela = func.current_date() - cast(func.concat(meses, " months"), Interval)

        descartes = _descartes_com_valor().where(
            StockProduct.stock_id == stock_id,
            Discard.date >= janela,
        ).subquery()

        mes = _competencia(descartes.c.data)

        stmt = (
            select(mes.label("mes"), func.coalesce(func.sum(descartes.c.valor), 0))
            .group_by(mes)
            .order_by(mes.asc())
        )

        return [
            {"mes": competencia, "valor_descartado": float(valor)}
            for competencia, valor in s.execute(stmt)
        ]


_financeiro = _FinanceiroPostgresRepo()


def gastos_por_mes(stock_id: int, meses: Sequence[str]) -> dict[str, float]:
    return _financeiro.gastos_por_mes(stock_id, meses)


def valor_descartado_do_mes(stock_id: int, mes: str) -> float:
    return _financeiro.valor_descartado_do_mes(stock_id, mes)


def evolucao_desperdicio(stock_id: int, meses: int) -> list[PontoDesperdicio]:
    return _financeiro.evolucao_desperdicio(stock_id, meses)


__all__ = [
    "PontoDesperdicio",
    "evolucao_desperdicio",
    "gastos_por_mes",
    "valor_descartado_do_mes",
]
