"""Preferências e receitas consultadas em um único turno da integração com o Core."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class RecipeTurn:
    preferences: frozenset[str]
    candidates: dict[int, str] = field(default_factory=dict)
    recipes: dict[int, str] = field(default_factory=dict)

    def exclusoes(self) -> tuple[list[str], list[str]]:
        categorias: set[str] = set()
        termos: set[str] = set()
        escolhas = self.preferences
        if escolhas & {"VEGETARIAN", "VEGAN"}:
            categorias.add("Carne")
            termos.update({"peixe", "camarão", "atum", "sardinha", "salmão", "bacalhau", "gelatina"})
        if escolhas & {"VEGAN", "NO_LACTOSE"}:
            categorias.add("Laticínio")
        if "VEGAN" in escolhas:
            termos.update({"ovo", "mel", "manteiga", "queijo", "leite", "creme de leite"})
        if "NO_RED_MEAT" in escolhas:
            termos.update({"bovin", "carne", "porco", "suín", "bacon", "presunto", "linguiça", "cordeiro"})
        if "NO_SEAFOOD" in escolhas:
            termos.update({"peixe", "camarão", "atum", "sardinha", "salmão", "bacalhau", "lula", "polvo", "ostra", "marisco"})
        if "NO_GLUTEN" in escolhas:
            termos.update({"trigo", "cevada", "centeio", "macarrão", "pão", "biscoito", "cerveja"})
        if "NO_SUGAR" in escolhas:
            termos.update({"açúcar", "açucar", "mel", "xarope", "leite condensado"})
        return sorted(categorias), sorted(termos)


_turno: ContextVar[RecipeTurn | None] = ContextVar("core_recipe_turn", default=None)


def turno_atual() -> RecipeTurn | None:
    return _turno.get()


@contextmanager
def turno_de_receitas(preferences: list[str]):
    turno = RecipeTurn(frozenset(preferences))
    token = _turno.set(turno)
    try:
        yield turno
    finally:
        _turno.reset(token)
