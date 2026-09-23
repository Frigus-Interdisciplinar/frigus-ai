from datetime import date

from pydantic import BaseModel, Field, model_validator

from frigus_ai.graph.tools.estoque.schemas import Category, StoragePlace


class StockItemCreate(BaseModel):
    product_name: str = Field(min_length=1)
    category: Category
    storage_place: StoragePlace
    quantity: int = Field(gt=0)
    expire_date: date
    unit_price: float = 0.0
    minimal_quantity: int | None = None


class StockItemCreateResponse(BaseModel):
    stock_product_id: int
    quantity: int
    product_status: str


class StockItemResponse(BaseModel):
    stock_product_id: int
    product_name: str
    category: str
    storage_place: str
    quantity: int
    minimal_quantity: int | None
    expire_date: str
    product_status: str | None
    unit_price: float


class StockItemUpdate(BaseModel):
    delta: int | None = None
    novo_valor: int | None = None

    @model_validator(mode="after")
    def _delta_ou_novo_valor(self):
        if (self.delta is None) == (self.novo_valor is None):
            raise ValueError("Informe 'delta' OU 'novo_valor', nunca os dois nem nenhum.")
        if self.novo_valor is not None and self.novo_valor < 0:
            raise ValueError("'novo_valor' não pode ser negativo.")
        return self


class StockItemQuantityResponse(BaseModel):
    stock_product_id: int
    quantity: int


class StockItemDiscardResponse(BaseModel):
    stock_product_id: int
    reason: str


class FotoAnaliseResponse(BaseModel):
    resposta: str
