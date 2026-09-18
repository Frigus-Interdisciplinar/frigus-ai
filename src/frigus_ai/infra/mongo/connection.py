from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings


class MongoConn(Connector[MongoClient[dict[str, Any]]]):
    def __init__(self) -> None:
        self._client: MongoClient[dict[str, Any]] | None = None

    def connect(self) -> MongoClient[dict[str, Any]]:
        if self._client is None:
            self._client = MongoClient(settings.MONGODB_URI)
        return self._client

    @property
    def client(self) -> MongoClient[dict[str, Any]]:
        return self.connect()

    @property
    def banco(self) -> Database[dict[str, Any]]:
        return self.client["frigus_ai"]

    def collection(self, name: str):
        return self.banco[name]


mongo = MongoConn()

__all__ = ["MongoConn", "mongo"]
