"""Ingestão do PDF de FAQ para a collection do Qdrant. Rodar sob demanda:
python -m frigus_ai.tools.qdrant.faq.ingest
"""

from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config.logging import get_logger
from config.models import Model
from config.settings import settings

from .connection import get_qdrant_client

logger = get_logger("qdrant_faq_ingest")

_PDF_PATH = Path("data/pdf/Frigus-Documentacao.pdf")
_CHUNK_SIZE = 700
_CHUNK_OVERLAP = 150
_TASK_TYPE_DOCUMENT = "retrieval_document"


def _load_chunks() -> list:
    loader = PyPDFLoader(_PDF_PATH)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=_CHUNK_SIZE,
        chunk_overlap=_CHUNK_OVERLAP,
    )
    return text_splitter.split_documents(loader.load())


def _ensure_collection_exists(client: QdrantClient, vector_size: int) -> None:
    if not client.collection_exists(settings.QDRANT_COLLECTION_NAME):
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def ingest() -> None:
    client = get_qdrant_client()
    chunks = _load_chunks()

    embeddings = GoogleGenerativeAIEmbeddings(
        model=Model.EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        task_type=_TASK_TYPE_DOCUMENT,
    )
    textos = [chunk.page_content for chunk in chunks]
    vetores = embeddings.embed_documents(textos)

    # Tamanho do vetor lido do embedding real, não fixado à mão — evita divergir
    # silenciosamente se o modelo mudar a dimensão de saída (gemini-embedding-001
    # não documenta um default fixo, depende de output_dimensionality).
    _ensure_collection_exists(client, vector_size=len(vetores[0]))

    pontos = [
        PointStruct(
            id=str(uuid5(NAMESPACE_DNS, texto)),
            vector=vetor,
            payload={
                "text": chunk.page_content,
                "file": chunk.metadata.get("source", ""),
                "page": chunk.metadata.get("page", 0),
            },
        )
        for texto, vetor, chunk in zip(textos, vetores, chunks, strict=True)
    ]

    client.upsert(collection_name=settings.QDRANT_COLLECTION_NAME, points=pontos)

    logger.info("INGESTÃO OK | collection=%s chunks=%d", settings.QDRANT_COLLECTION_NAME, len(chunks))


if __name__ == "__main__":
    ingest()
