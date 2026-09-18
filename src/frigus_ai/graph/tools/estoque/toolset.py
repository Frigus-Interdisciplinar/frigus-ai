"""Compatibilidade temporária; use ``repo.EstoqueRepo``."""

from .repo import EstoqueRepo

EstoqueToolSet = EstoqueRepo

__all__ = ["EstoqueToolSet"]
