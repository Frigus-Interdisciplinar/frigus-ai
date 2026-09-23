"""Compatibilidade temporária; use ``repo.SpoonacularRepo``."""

import time

from frigus_ai.infra.spoonacular.connection import spoonacular
from frigus_ai.settings import settings

from .repo import _TTL_SEGUNDOS, SpoonacularRepo, _get

SpoonacularToolSet = SpoonacularRepo

__all__ = ["_TTL_SEGUNDOS", "SpoonacularToolSet", "_get", "settings", "spoonacular", "time"]
