from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_id(cur, table: str) -> int:
    """
    A maioria das tabelas do schema `dataload` usa INTEGER PRIMARY KEY sem
    SERIAL/IDENTITY (o DDL foi pensado para carga de dados, não para inserts
    incrementais de app). Para inserts vindos do chatbot, geramos o próximo ID
    disponível na hora. Não é seguro contra concorrência pesada, mas é
    suficiente para o escopo deste assistente.

    Versão cursor cru — só pro domínio ainda não migrado pra SQLAlchemy (compras).
    Repositories novos usam `proximo_id`.
    """

    cur.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table};")
    return cur.fetchone()[0]


def proximo_id(session: Session, model: type) -> int:
    """Equivalente SQLAlchemy de `next_id`, pros repositories que já usam `PostgresRepo`."""

    return (session.scalar(select(func.coalesce(func.max(model.id), 0))) or 0) + 1


__all__ = ["next_id", "proximo_id"]
