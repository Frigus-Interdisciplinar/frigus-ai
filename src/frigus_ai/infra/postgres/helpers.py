from sqlalchemy import func, select
from sqlalchemy.orm import Session


def proximo_id(session: Session, model: type) -> int:
    """
    A maioria das tabelas do schema `dataload` usa INTEGER PRIMARY KEY sem
    SERIAL/IDENTITY (o DDL foi pensado para carga de dados, não para inserts
    incrementais de app). Para inserts vindos do chatbot, geramos o próximo ID
    disponível na hora. Não é seguro contra concorrência pesada, mas é
    suficiente para o escopo deste assistente.
    """

    return (session.scalar(select(func.coalesce(func.max(model.id), 0))) or 0) + 1


__all__ = ["proximo_id"]
