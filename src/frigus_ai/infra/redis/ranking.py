"""
Ranking de itens mais desperdiçados por estoque, via sorted set do Redis
(`ZINCRBY`/`ZREVRANGE`) — a fila/ranking em tempo real que o enunciado pede além de
cache e rate limit.

Alimentado por `graph/tools/estoque/repo.py` (discard_product), depois que o descarte já
foi commitado no Postgres — o Redis é só a estatística agregada, nunca a fonte de
verdade do desperdício (essa é `discard`/`stock_movements`, via financeiro_repository).
"""

from typing import NamedTuple, cast

from frigus_ai.infra.redis.connection import get_client
from frigus_ai.infra.redis.keys import _chave_ranking_desperdicio


class ItemRanking(NamedTuple):
    produto: str
    quantidade: float


def registrar_descarte(stock_id: int, product_name: str, quantidade: int) -> None:
    get_client().zincrby(_chave_ranking_desperdicio(stock_id), quantidade, product_name)


def top_desperdicio(stock_id: int, limit: int = 5) -> list[ItemRanking]:
    """Produtos mais descartados, do maior pro menor."""

    # zrevrange(..., withscores=True) devolve list[tuple[str, float]] em runtime — o stub do
    # redis-py só resolve isso com Literal[True], não com bool genérico, daí o cast.
    resultado = get_client().zrevrange(_chave_ranking_desperdicio(stock_id), 0, limit - 1, withscores=True)
    return [ItemRanking(*item) for item in cast(list[tuple[str, float]], resultado)]


__all__ = ["ItemRanking", "registrar_descarte", "top_desperdicio"]
