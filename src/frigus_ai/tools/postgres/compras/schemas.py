from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "Fruta", "Verdura", "Laticínio", "Carne", "Grão",
    "Bebida", "Limpeza", "Higiene Pessoal",
]
StoragePlace = Literal["Geladeira", "Freezer", "Despensa", "Armário", "Prateleira"]
ItemStatus = Literal["Pendente", "Comprado", "Removido"]


class AddShoppingListProductArgs(BaseModel):
    product_name: str = Field(description="Nome do produto a adicionar na lista de compras.")
    category: Category = Field(description="Categoria do produto (necessária se ele ainda não existir no catálogo).")
    storage_place: StoragePlace = Field(description="Local onde o produto costuma ser guardado (necessário se ele ainda não existir no catálogo).")
    quantity: int = Field(default=1, ge=1, description="Quantidade desejada.")


class QueryShoppingListArgs(BaseModel):
    status: ItemStatus | None = Field(default=None, description="Filtra itens por status. Sem filtro, retorna Pendente e Comprado.")


class MarkPurchasedArgs(BaseModel):
    shopping_list_product_id: int | None = Field(default=None, description="ID direto do item na lista, se conhecido.")
    product_name: str | None = Field(default=None, description="Nome (ou parte) do produto, usado se o ID não for informado.")
    status: Literal["Comprado", "Removido"] = Field(default="Comprado", description="Novo status do item: Comprado ou Removido.")


class GenerateShoppingListFromLowStockArgs(BaseModel):
    pass

