"""Compatibilidade temporária; use ``repo.ComprasRepo``."""

from .repo import ComprasRepo

ComprasToolSet = ComprasRepo

__all__ = ["ComprasToolSet"]
