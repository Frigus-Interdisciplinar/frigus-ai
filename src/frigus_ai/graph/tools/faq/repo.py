from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.qdrant.connection import get_embeddings, get_qdrant_client
from frigus_ai.settings import settings

from .schemas import FaqRetrieverArgs, SearchResponse

_K_NUMBER = 5
_TASK_TYPE_QUERY = "retrieval_query"


class FaqRepo(ToolSet):
    def faq_retriever(self, question: str) -> dict:
        """Consulta a documentação oficial do Frigus para dúvidas sobre o aplicativo."""

        client = get_qdrant_client()

        vetor = get_embeddings(_TASK_TYPE_QUERY).embed_query(question)

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

        return Response.ok(results=[r.model_dump() for r in resultados])

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                self.faq_retriever, name="faq_retriever", args_schema=FaqRetrieverArgs
            ),
        ]


__all__ = ["FaqRepo"]
