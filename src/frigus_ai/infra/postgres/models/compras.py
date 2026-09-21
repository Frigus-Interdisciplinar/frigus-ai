from datetime import date

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

ListStatusEnum = Enum("Aberta", "Concluída", "Cancelada", name="list_status_enum")
ProductListStatusEnum = Enum("Pendente", "Comprado", "Removido", name="product_list_status_enum")


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    date: Mapped[date]
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(ListStatusEnum)


class ShoppingListProduct(Base):
    __tablename__ = "shopping_list_products"
    __table_args__ = (
        UniqueConstraint("list_id", "product_id", name="uq_shopping_list_products_list_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    status: Mapped[str | None] = mapped_column(ProductListStatusEnum)
    quantity: Mapped[int]


__all__ = ["ShoppingList", "ShoppingListProduct"]
