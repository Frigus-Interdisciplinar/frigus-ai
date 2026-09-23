from pydantic import BaseModel, Field

from frigus_ai.repositories.preferencias_repository import TipoPreferencia


class ListarPreferenciasArgs(BaseModel):
    pass


class DefinirPreferenciaArgs(BaseModel):
    ingrediente_nome: str = Field(description="Nome do ingrediente, ex: 'Coentro'.")
    tipo: TipoPreferencia = Field(
        description="Tipo da preferência: prefers (gosta), dislikes (não gosta) ou "
        "allergic_to (é alérgico)."
    )


class RemoverPreferenciaArgs(DefinirPreferenciaArgs):
    pass


class SugerirReceitasCompativeisArgs(BaseModel):
    limit: int = Field(default=10, description="Número máximo de receitas a retornar.")
