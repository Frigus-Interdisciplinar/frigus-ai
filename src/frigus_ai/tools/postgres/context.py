"""
Contexto de sessão (user_id/stock_id) propagado via contextvars.

As tools nunca recebem stock_id como argumento do LLM — ele é resolvido uma vez
por turno (users -> user_groups -> groups -> stocks, ver helpers.resolve_stock_id)
e injetado aqui antes de invocar o grafo, evitando que o modelo tenha que
adivinhar ou inventar IDs de estoque.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

_current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)
_current_stock_id: ContextVar[Optional[int]] = ContextVar("current_stock_id", default=None)


@contextmanager
def session_context(user_id: int, stock_id: Optional[int]):
    token_user = _current_user_id.set(user_id)
    token_stock = _current_stock_id.set(stock_id)
    try:
        yield
    finally:
        _current_user_id.reset(token_user)
        _current_stock_id.reset(token_stock)


def current_user_id() -> int:
    value = _current_user_id.get()
    if value is None:
        raise RuntimeError("current_user_id não definido — chame dentro de session_context().")
    return value


def current_stock_id() -> int:
    value = _current_stock_id.get()
    if value is None:
        raise RuntimeError("current_stock_id não definido — usuário sem grupo/estoque associado.")
    return value


__all__ = ["session_context", "current_user_id", "current_stock_id"]
