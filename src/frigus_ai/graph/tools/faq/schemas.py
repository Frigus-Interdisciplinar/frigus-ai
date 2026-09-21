from pydantic import BaseModel, Field


class FaqRetrieverArgs(BaseModel):
    question: str = Field(description="Pergunta do usuário sobre o funcionamento do app Frigus.")


class SearchResponse(BaseModel):
    text: str
    file: str
    page: int
    score: float
