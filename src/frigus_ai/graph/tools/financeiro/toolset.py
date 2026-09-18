"""Compatibilidade temporária; use ``repo.FinanceiroRepo``."""

from .repo import FinanceiroRepo

FinanceiroToolSet = FinanceiroRepo

__all__ = ["FinanceiroToolSet"]
