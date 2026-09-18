"""Compatibilidade temporária; use ``repo.ReceitasRepo``."""

from .repo import ReceitasRepo

ReceitasToolSet = ReceitasRepo

__all__ = ["ReceitasToolSet"]
