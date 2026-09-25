import functools
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings


class PostgresConn(Connector[Engine]):
    """Engine SQLAlchemy síncrono, lazy — todo repository fala com o Postgres por aqui
    via `PostgresRepo`/`@transacional`. Tabelas no schema `public` do
    Supabase (search_path padrão), mapeadas em `infra/postgres/models/`."""

    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def connect(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(settings.POSTGRES_URI)
        return self._engine

    @property
    def _factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.connect())

        return self._session_factory

    @contextmanager
    def session(self) -> Generator[Session]:
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


__all__ = ["PostgresConn", "PostgresRepo", "postgres", "transacional"]
