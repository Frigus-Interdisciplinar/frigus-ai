from typing import Literal

from pydantic import BaseModel, Field

from frigus_ai.tools.postgres.helpers import CATEGORY_VALUES, STORAGE_PLACE_VALUES

Category = Literal[
    "Fruta", "Verdura", "Laticínio", "Carne", "Grão",
    "Bebida", "Limpeza", "Higiene Pessoal",
]
StoragePlace = Literal["Geladeira", "Freezer", "Despensa", "Armário", "Prateleira"]
ProductStatus = Literal["Fresco", "Próximo do vencimento", "Vencido"]


class AddStockProductArgs(BaseModel):
    product_name: str = Field(..., description="Nome do produto (ex.: 'Leite integral', 'Peito de frango').")
    category: Category = Field(..., description=f"Categoria do produto. Uma de: {', '.join(CATEGORY_VALUES)}.")
    storage_place: StoragePlace = Field(..., description=f"Onde o produto é guardado. Uma de: {', '.join(STORAGE_PLACE_VALUES)}.")
    quantity: int = Field(..., description="Quantidade de unidades adicionadas ao estoque.")
    expire_date: str = Field(..., description="Data de validade no formato YYYY-MM-DD.")
    unit_price: float = Field(default=0.0, description="Preço unitário pago (usado para o módulo financeiro).")
    minimal_quantity: int | None = Field(default=None, description="Quantidade mínima antes de sugerir recompra (opcional).")


class QueryStockArgs(BaseModel):
    storage_place: StoragePlace | None = Field(default=None, description="Filtra por local de armazenamento.")
    category: Category | None = Field(default=None, description="Filtra por categoria do produto.")
    product_status: ProductStatus | None = Field(default=None, description="Filtra pelo semáforo de validade.")
    vencendo_em_dias: int | None = Field(default=None, description="Retorna apenas itens que vencem em até N dias.")
    product_name: str | None = Field(default=None, description="Busca por texto no nome do produto.")


class UpdateStockQuantityArgs(BaseModel):
    stock_product_id: int | None = Field(default=None, description="ID direto do item no estoque, se conhecido.")
    product_name: str | None = Field(default=None, description="Nome (ou parte) do produto, usado se stock_product_id não for informado.")
    delta: int | None = Field(default=None, description="Variação da quantidade (negativo para consumo, positivo para reposição).")
    novo_valor: int | None = Field(default=None, description="Define a quantidade final diretamente (alternativa a delta).")


class DiscardProductArgs(BaseModel):
    stock_product_id: int | None = Field(default=None, description="ID direto do item no estoque, se conhecido.")
    product_name: str | None = Field(default=None, description="Nome (ou parte) do produto, usado se stock_product_id não for informado.")
    reason: str = Field(default="Vencido", description="Motivo do descarte (ex.: 'Vencido', 'Estragou', 'Mofou').")
