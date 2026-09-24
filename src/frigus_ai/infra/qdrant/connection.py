from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from qdrant_client import AsyncQdrantClient, QdrantClient

from frigus_ai.infra.base import Connector
from frigus_ai.models import Model
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


class AsyncQdrantConn(Connector[AsyncQdrantClient]):
    """Pra quem roda dentro do event loop (memória de chats). O FAQ fica no síncrono: as
    tools dele são `def`, e o LangChain já as joga numa thread."""

    def __init__(self) -> None:
        self._client: AsyncQdrantClient | None = None

    def connect(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
            )
        return self._client

    @property
    def client(self) -> AsyncQdrantClient:
        return self.connect()


qdrant = QdrantConn()
qdrant_async = AsyncQdrantConn()


def get_qdrant_client() -> QdrantClient:
    return qdrant.client


def get_async_qdrant_client() -> AsyncQdrantClient:
    return qdrant_async.client


@lru_cache(maxsize=2)
def get_embeddings(task_type: str) -> GoogleGenerativeAIEmbeddings:
    """Embedding de tudo que vai pro Qdrant. `task_type`: "retrieval_document" pra
    indexar, "retrieval_query" pra buscar — o Gemini otimiza o vetor pra cada lado."""

    return GoogleGenerativeAIEmbeddings(
        model=Model.EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        task_type=task_type,
    )


__all__ = [
    "AsyncQdrantConn",
    "QdrantConn",
    "get_async_qdrant_client",
    "get_embeddings",
    "get_qdrant_client",
    "qdrant",
    "qdrant_async",
]
