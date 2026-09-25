from datetime import date

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import UUID_DEFAULT, Base, UuidStr, rotulo

ListStatusEnum = rotulo(["Aberta", "Concluída", "Cancelada"], ["OPEN", "COMPLETED", "CANCELED"])
ProductListStatusEnum = rotulo(["Pendente", "Comprado", "Removido"], ["PENDING", "PURCHASED", "REMOVED"])


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[UuidStr] = mapped_column(primary_key=True, server_default=UUID_DEFAULT)
    date: Mapped[date]
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(ListStatusEnum)


class ShoppingListProduct(Base):
    __tablename__ = "shopping_list_products"
    __table_args__ = (
        UniqueConstraint("list_id", "product_id", name="uq_shopping_list_products_list_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[UuidStr] = mapped_column(ForeignKey("shopping_lists.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    status: Mapped[str | None] = mapped_column(ProductListStatusEnum)
    quantity: Mapped[int]


__all__ = ["ShoppingList", "ShoppingListProduct"]
