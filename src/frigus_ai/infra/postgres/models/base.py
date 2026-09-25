from typing import Annotated

from sqlalchemy import String, TypeDecorator, Uuid, text
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    """
    Tabelas no schema `public` do Supabase (banco real do grupo) — sem schema explícito,
    cai no search_path padrão da conexão.
    """


# UUID do Supabase como `str` no app — é assim que Mongo/Redis/Qdrant já guardam o user_id.
UuidStr = Annotated[str, mapped_column(Uuid(as_uuid=False))]
UUID_DEFAULT = text("gen_random_uuid()")


class Rotulo(TypeDecorator[str]):
    """
    O Supabase guarda os "enums" como VARCHAR com código em inglês (`FRUIT`, `OPEN`, ...),
    mas o app inteiro (tools, prompts, respostas) fala o rótulo em português (`Fruta`,
    `Aberta`). A tradução acontece só aqui, na coluna — bind e resultado, inclusive em
    WHERE e ON CONFLICT. Valor sem par passa direto.
    """

    impl = String
    cache_ok = True

    def __init__(self, pares: tuple[tuple[str, str], ...]) -> None:
        super().__init__()
        self.pares = pares
        self._para_codigo = dict(pares)
        self._para_rotulo = {codigo: rotulo for rotulo, codigo in pares}

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return self._para_codigo.get(value, value) if value is not None else None

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return self._para_rotulo.get(value, value) if value is not None else None


def rotulo(rotulos: list[str], codigos: list[str]) -> Rotulo:
    return Rotulo(tuple(zip(rotulos, codigos, strict=True)))
