from typing import Optional, Literal
from pydantic import BaseModel, Field

Category = Literal[
    "Fruta", "Verdura", "Laticínio", "Carne", "Grão",
    "Bebida", "Limpeza", "Higiene Pessoal",
]
StoragePlace = Literal["Geladeira", "Freezer", "Despensa", "Armário", "Prateleira"]
ItemStatus = Literal["Pendente", "Comprado", "Removido"]


class AddShoppingListProductArgs(BaseModel):
    product_name: str = Field(..., description="Nome do produto a adicionar na lista de compras.")
    category: Category = Field(..., description="Categoria do produto (necessária se ele ainda não existir no catálogo).")
    storage_place: StoragePlace = Field(..., description="Local onde o produto costuma ser guardado (necessário se ele ainda não existir no catálogo).")
    quantity: int = Field(default=1, description="Quantidade desejada.")


class QueryShoppingListArgs(BaseModel):
    status: Optional[ItemStatus] = Field(default=None, description="Filtra itens por status. Sem filtro, retorna Pendente e Comprado.")


class MarkPurchasedArgs(BaseModel):
    shopping_list_product_id: Optional[int] = Field(default=None, description="ID direto do item na lista, se conhecido.")
    product_name: Optional[str] = Field(default=None, description="Nome (ou parte) do produto, usado se o ID não for informado.")
    status: ItemStatus = Field(default="Comprado", description="Novo status do item: Comprado ou Removido.")


class GenerateShoppingListFromLowStockArgs(BaseModel):
    pass


class RegisterPurchaseFromNfeArgs(BaseModel):
    nfe_key_or_url: str = Field(..., description="Chave de acesso ou URL do QR Code da NF-e (formato SEFAZ-SP).")
