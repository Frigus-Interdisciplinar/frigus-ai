
from pydantic import BaseModel, Field


class MesArgs(BaseModel):
    mes: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Mês no formato YYYY-MM. Se ausente, usa o mês atual.")


class EvolucaoDesperdicioArgs(BaseModel):
    meses: int = Field(default=6, ge=1, le=60, description="Quantos meses (contando o atual) considerar na série histórica.")
