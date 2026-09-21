from langchain_core.tools import BaseTool, StructuredTool
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.qdrant.connection import get_qdrant_client
from frigus_ai.logging import Logging
from frigus_ai.models import Model
from frigus_ai.settings import settings

from .schemas import FaqRetrieverArgs, SearchResponse

logger = Logging.get_logger("qdrant_faq")

_K_NUMBER = 5
_TASK_TYPE_QUERY = "retrieval_query"


class FaqRepo(ToolSet):
    def faq_retriever(self, question: str) -> dict:
        """Consulta a documentação oficial do Frigus para dúvidas sobre o aplicativo."""

        return self._faq_retriever(question)

    def _faq_retriever(self, question: str) -> dict:
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

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                self.faq_retriever, name="faq_retriever", args_schema=FaqRetrieverArgs
            ),
        ]


__all__ = ["FaqRepo"]
