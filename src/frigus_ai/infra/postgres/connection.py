import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from psycopg2 import pool
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings

# Todo o DDL (data/sql/schema.sql) mora no schema `dataload`, não em `public`. As tools
# de SQL cru (só compras, hoje) precisam do search_path na conexão;
# os models SQLAlchemy (infra/postgres/models/) já qualificam o schema no metadata, não
# precisam dele.
_SEARCH_PATH = "dataload"


class PostgresConn(Connector[pool.ThreadedConnectionPool]):
    """
    Guarda os dois clientes que o projeto usa contra o mesmo Postgres — o pool
    `psycopg2` (SQL cru, hoje só a tool de compras) e o engine SQLAlchemy síncrono
    (`PostgresRepo`/`@transacional`, usado por receitas, financeiro e estoque) — os dois
    lazy, nenhum conecta no import do módulo.

    A migração do SQL cru pro SQLAlchemy é incremental: só `compras` ainda usa o pool,
    então os dois clientes convivem até ela sair.
    """

    def __init__(self) -> None:
        self._pool: pool.ThreadedConnectionPool | None = None
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def connect(self) -> pool.ThreadedConnectionPool:
        if self._pool is None:
            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=settings.POSTGRES_URI,
                options=f"-c search_path={_SEARCH_PATH}",
            )
        return self._pool

    @contextmanager
    def connection(self) -> Iterator[Any]:
        conn = self.connect().getconn()
        try:
            yield conn
        finally:
            self.connect().putconn(conn)

    @property
    def _factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            self._engine = create_engine(settings.POSTGRES_URI)
            self._session_factory = sessionmaker(bind=self._engine)

        return self._session_factory

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Commit no sucesso, rollback na exceção, close sempre."""

        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()


postgres = PostgresConn()


def get_conn() -> Iterator[Any]:
    return postgres.connection()


def transacional[T](metodo: Callable[..., T]) -> Callable[..., T]:
    """Abre uma sessão SQLAlchemy, injeta como 2º argumento do método (`self` é o 1º),
    comita/reverte e fecha — tira o `with self.conn.session()` de dentro de cada método."""

    @functools.wraps(metodo)
    def wrapper(self: "PostgresRepo", *args: Any, **kwargs: Any) -> T:
        with self.conn.session() as s:
            return metodo(self, s, *args, **kwargs)

    return wrapper


class PostgresRepo:
    """Base dos repositories que falam com o Postgres via SQLAlchemy (`@transacional`)."""

    def __init__(self, conn: PostgresConn | None = None) -> None:
        self.conn = conn or postgres


__all__ = ["PostgresConn", "PostgresRepo", "get_conn", "postgres", "transacional"]
