from pydantic import BaseModel, Field

from frigus_ai.graph.tools.estoque.schemas import Category, StoragePlace


class ShoppingItemCreate(BaseModel):
    product_name: str = Field(min_length=1)
    quantity: int = Field(default=1, gt=0)
    category: Category | None = None
    storage_place: StoragePlace | None = None


class ShoppingItemCreateResponse(BaseModel):
    shopping_list_product_id: int
    quantity: int


class ShoppingItemResponse(BaseModel):
    shopping_list_product_id: int
    product_name: str
    category: str
    quantity: int
    status: str | None


class ShoppingItemBoughtResponse(BaseModel):
    shopping_list_product_id: int
    status: str
