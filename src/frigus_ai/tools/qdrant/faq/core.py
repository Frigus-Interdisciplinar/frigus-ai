from langchain.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from config.logging import get_logger
from config.models import Model
from config.settings import settings
from frigus_ai.tools.response import Response

from .connection import get_qdrant_client
from .schemas import FaqRetrieverArgs, SearchResponse

logger = get_logger("qdrant_faq")

_K_NUMBER = 5
_TASK_TYPE_QUERY = "retrieval_query"


@tool("faq_retriever", args_schema=FaqRetrieverArgs)
def faq_retriever(question: str) -> dict:
    """
    Consulta a documentação oficial do Frigus para dúvidas sobre o funcionamento do app.
    """

    try:
        client = get_qdrant_client()

        embeddings = GoogleGenerativeAIEmbeddings(
            model=Model.EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            task_type=_TASK_TYPE_QUERY,
        )
        vetor = embeddings.embed_query(question)

        pontos = client.query_points(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query=vetor,
            limit=_K_NUMBER,
        ).points

        resultados = [
            SearchResponse(
                text=p.payload["text"],
                file=p.payload["file"],
                page=p.payload["page"],
                score=p.score,
            )
            for p in pontos
        ]

        logger.info("FAQ OK | question=%r | resultados=%d", question, len(resultados))

        return Response.ok(results=[r.model_dump() for r in resultados])

    except Exception as e:
        logger.error("FAQ ERRO | %s", e)
        return Response.error(e)
