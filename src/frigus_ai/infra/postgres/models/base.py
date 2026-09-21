from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Metadata presa ao schema `dataload` (data/sql/schema.sql), não `public` —
    mesmo isolamento que `infra/postgres/connection.py` já faz via search_path.
    """

    metadata = MetaData(schema="dataload")
