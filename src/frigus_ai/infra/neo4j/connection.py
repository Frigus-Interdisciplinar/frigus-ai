from neomodel import adb, config
from neomodel.async_.database import AsyncDatabase

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings


class Neo4jConn(Connector[AsyncDatabase]):
    def __init__(self) -> None:
        self._connected = False

    def connect(self) -> AsyncDatabase:
        if not self._connected:
            config.DATABASE_URL = settings.NEO4J_URI
            self._connected = True
        return adb

    @property
    def client(self) -> AsyncDatabase:
        return self.connect()


neo4j = Neo4jConn()

__all__ = ["Neo4jConn", "neo4j"]
