"""Compatibilidade temporária; use ``repo.FaqRepo``."""

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from frigus_ai.infra.qdrant.connection import get_qdrant_client
from frigus_ai.settings import settings

from . import repo
from .repo import FaqRepo


class FaqToolSet(FaqRepo):
   def faq_retriever(self, question: str) -> dict:
       """Consulta a documentação oficial do Frigus para dúvidas sobre o aplicativo."""

       repo.get_qdrant_client = get_qdrant_client
       repo.GoogleGenerativeAIEmbeddings = GoogleGenerativeAIEmbeddings
       repo.settings = settings
       return super().faq_retriever(question)


__all__ = ["FaqToolSet"]
