from qdrant_client import QdrantClient

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings


class QdrantConn(Connector[QdrantClient]):
    def __init__(self) -> None:
        self._client: QdrantClient | None = None

    def connect(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
            )
        return self._client

    @property
    def client(self) -> QdrantClient:
        return self.connect()


qdrant = QdrantConn()


def get_qdrant_client() -> QdrantClient:
    return qdrant.client


__all__ = ["QdrantConn", "get_qdrant_client", "qdrant"]
