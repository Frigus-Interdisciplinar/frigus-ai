from pathlib import Path
from langchain.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from config.settings import settings
from config.models import Model
from config.logging import get_logger

log = get_logger(__name__)


_PDF_PATH      = Path("data/Frigus-Documentacao.pdf")
_CHUNK_SIZE    = 700
_CHUNK_OVERLAP = 150
_K_NUMBER      = 5

_index: FAISS | None = None


def _get_index() -> FAISS:
    global _index

    if _index is None:
        loader = PyPDFLoader(_PDF_PATH)
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=_CHUNK_SIZE,
            chunk_overlap=_CHUNK_OVERLAP
        ).split_documents(loader.load())

        embeddings = GoogleGenerativeAIEmbeddings(
            model=Model.EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            task_type="retrieval_document"
        )

        _index = FAISS.from_documents(chunks, embeddings)

    return _index


@tool("faq_retriever")
def faq_retriever(question: str) -> str:
    """
    Consulta a documentação oficial do Frigus para dúvidas sobre o funcionamento do app.
    """

    log.debug(f"FAQ consultado | question: {question}")

    results = _get_index().similarity_search(question, k=_K_NUMBER)
    return "\n\n".join(res.page_content for res in results)
