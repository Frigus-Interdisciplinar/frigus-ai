from pydantic import BaseModel, Field


class SugerirReceitasCompativeisArgs(BaseModel):
    evitar: list[str] | None = Field(
        default=None,
        description="Ingredientes que o usuário não gosta, ex: ['Coentro']. As alergias do "
        "perfil já entram automaticamente, não precisa repeti-las.",
    )
    limit: int = Field(default=10, description="Número máximo de receitas a retornar.")
