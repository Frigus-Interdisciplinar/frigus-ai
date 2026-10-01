"""Scripts Lua (atômicos no Redis) em `lua/`, lidos uma vez no import."""

from pathlib import Path

_DIR = Path(__file__).parent / "lua"


def _ler(nome: str) -> str:
    return (_DIR / f"{nome}.lua").read_text(encoding="utf-8")


ALOCAR_KEY = _ler("alocar_key")
ROTACIONAR_KEY = _ler("rotacionar_key")
REVOGAR_KEY = _ler("revogar_key")

__all__ = ["ALOCAR_KEY", "REVOGAR_KEY", "ROTACIONAR_KEY"]
