from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UuidStr, rotulo

# Rótulos em português que o app usa — fonte única, reaproveitada
# por graph/tools/estoque/helpers.py pra normalizar entrada em linguagem natural do LLM.
# Mora aqui (infra) e não lá (domínio) porque os models não podem depender de graph/tools
# — senão qualquer import de infra.postgres.models arrasta o pacote de tools inteiro.
CATEGORY_VALUES = [
    "Fruta", "Verdura", "Laticínio", "Carne", "Grão",
    "Bebida", "Limpeza", "Higiene Pessoal",
]

STORAGE_PLACE_VALUES = ["Geladeira", "Freezer", "Despensa", "Armário", "Prateleira"]

VENCIDO = "Vencido"
PRODUCT_STATUS_VALUES = ["Fresco", "Próximo do vencimento", VENCIDO]

ENTRADA = "Entrada"
SAIDA = "Saída"
AJUSTE = "Ajuste"
MOVEMENT_TYPE_VALUES = [ENTRADA, SAIDA, AJUSTE]

# Mesma ordem dos rótulos acima: o código em inglês que o Supabase grava (ver `base.Rotulo`).
CategoryEnum = rotulo(CATEGORY_VALUES, [
    "FRUIT", "VEGETABLE", "DAIRY", "MEAT", "GRAIN",
    "BEVERAGE", "CLEANING", "PERSONAL_HYGIENE",
])
StoragePlaceEnum = rotulo(STORAGE_PLACE_VALUES, ["FRIDGE", "FREEZER", "PANTRY", "CABINET", "SHELF"])
ProductStatusEnum = rotulo(PRODUCT_STATUS_VALUES, ["FRESH", "NEAR_EXPIRATION", "EXPIRED"])
MovementTypeEnum = rotulo(MOVEMENT_TYPE_VALUES, ["IN", "OUT", "ADJUSTMENT"])


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    category: Mapped[str] = mapped_column(CategoryEnum)
    storage_place: Mapped[str] = mapped_column(StoragePlaceEnum)
    unit_price: Mapped[Decimal] = mapped_column(Numeric)
    unit_of_measure: Mapped[str] = mapped_column(default="UNIT")


class StockProduct(Base):
    __tablename__ = "stock_products"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "stock_id", "expire_date", name="uq_stock_products_product_stock_expire"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"))
    quantity: Mapped[int]
    minimal_quantity: Mapped[int | None]
    expire_date: Mapped[date]
    product_status: Mapped[str | None] = mapped_column(ProductStatusEnum)
    category: Mapped[str] = mapped_column(CategoryEnum)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_product_id: Mapped[int] = mapped_column(ForeignKey("stock_products.id", ondelete="CASCADE"))
    user_id: Mapped[UuidStr] = mapped_column(ForeignKey("users.id"))
    movement_type: Mapped[str] = mapped_column(MovementTypeEnum)
    quantity: Mapped[int]
    date: Mapped[datetime | None] = mapped_column(server_default=func.now())


class Discard(Base):
    __tablename__ = "discard"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_product_id: Mapped[int] = mapped_column(ForeignKey("stock_products.id", ondelete="CASCADE"))
    reason: Mapped[str | None]
    date: Mapped[datetime] = mapped_column(server_default=func.now())


__all__ = [
    "AJUSTE",
    "CATEGORY_VALUES",
    "ENTRADA",
    "MOVEMENT_TYPE_VALUES",
    "PRODUCT_STATUS_VALUES",
    "SAIDA",
    "STORAGE_PLACE_VALUES",
    "VENCIDO",
    "Discard",
    "Product",
    "StockMovement",
    "StockProduct",
]
