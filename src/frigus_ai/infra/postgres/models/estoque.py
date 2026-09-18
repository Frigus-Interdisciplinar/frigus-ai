from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Valores exatos dos enums do schema (data/sql/schema.sql) — fonte única, reaproveitada
# por graph/tools/estoque/helpers.py pra normalizar entrada em linguagem natural do LLM.
# Mora aqui (infra) e não lá (domínio) porque os models não podem depender de graph/tools
# — senão qualquer import de infra.postgres.models arrasta o pacote de tools inteiro.
CATEGORY_VALUES = [
    "Fruta", "Verdura", "Laticínio", "Carne", "Grão",
    "Bebida", "Limpeza", "Higiene Pessoal",
]

STORAGE_PLACE_VALUES = ["Geladeira", "Freezer", "Despensa", "Armário", "Prateleira"]

PRODUCT_STATUS_VALUES = ["Fresco", "Próximo do vencimento", "Vencido"]

CategoryEnum = Enum(*CATEGORY_VALUES, name="category_enum")
StoragePlaceEnum = Enum(*STORAGE_PLACE_VALUES, name="storage_place_enum")
ProductStatusEnum = Enum(*PRODUCT_STATUS_VALUES, name="product_status_enum")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str]
    category: Mapped[str] = mapped_column(CategoryEnum)
    storage_place: Mapped[str] = mapped_column(StoragePlaceEnum)
    unit_price: Mapped[Decimal] = mapped_column(Numeric)


class StockProduct(Base):
    __tablename__ = "stock_products"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "stock_id", "expire_date", name="uq_stock_products_product_stock_expire"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"))
    quantity: Mapped[int]
    minimal_quantity: Mapped[int | None]
    expire_date: Mapped[date]
    product_status: Mapped[str | None] = mapped_column(ProductStatusEnum)
    category: Mapped[str] = mapped_column(CategoryEnum)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)  # SERIAL no schema
    stock_product_id: Mapped[int] = mapped_column(ForeignKey("stock_products.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    movement_type: Mapped[str] = mapped_column(Enum("Entrada", "Saída", "Ajuste", name="movement_type_enum"))
    quantity: Mapped[int]
    date: Mapped[datetime | None]


class Discard(Base):
    __tablename__ = "discard"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    stock_product_id: Mapped[int] = mapped_column(ForeignKey("stock_products.id", ondelete="CASCADE"))
    reason: Mapped[str | None]
    date: Mapped[datetime]


__all__ = [
    "CATEGORY_VALUES",
    "PRODUCT_STATUS_VALUES",
    "STORAGE_PLACE_VALUES",
    "Discard",
    "Product",
    "StockMovement",
    "StockProduct",
]
