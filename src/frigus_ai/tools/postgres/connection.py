import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from config.settings import settings

# Todo o DDL (data/sql/schema.sql) mora no schema `dataload`, não em `public`.
# Toda conexão precisa forçar esse search_path, senão as tabelas não são encontradas.
_SEARCH_PATH = "dataload"

_pool = None


def _get_pool() -> pool.ThreadedConnectionPool:

    global _pool

    if _pool is None:
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.DATABASE_URI,
            options=f"-c search_path={_SEARCH_PATH}",
        )

    return _pool


@contextmanager
def get_conn():

    conn = _get_pool().getconn()
    try:
        yield conn
    finally:
        _get_pool().putconn(conn)
