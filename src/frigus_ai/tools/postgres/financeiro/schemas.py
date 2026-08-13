
from pydantic import BaseModel, Field


class MesArgs(BaseModel):
    mes: str | None = Field(default=None, description="Mês no formato YYYY-MM. Se ausente, usa o mês atual.")


class EvolucaoDesperdicioArgs(BaseModel):
    meses: int = Field(default=6, description="Quantos meses (contando o atual) considerar na série histórica.")
