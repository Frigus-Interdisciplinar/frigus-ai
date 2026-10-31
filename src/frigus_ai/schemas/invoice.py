"""Contrato de enriquecimento de produtos de NFC-e para revisão de estoque."""

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "FRUIT", "VEGETABLE", "DAIRY", "GRAIN", "MEAT", "BEVERAGE", "CLEANING",
    "PERSONAL_HYGIENE", "FISH", "FROZEN", "SWEETS", "CANNED", "SEASONING",
]
StoragePlace = Literal["FRIDGE", "FREEZER", "PANTRY", "CABINET", "SHELF"]
UnitOfMeasure = Literal["KILOGRAM", "GRAM", "LITER", "MILLILITER", "UNIT", "DOZEN", "PACKAGE"]


class InvoiceProductInput(BaseModel):
    lineNumber: int = Field(ge=1)
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(gt=0)
    unit: str | None = Field(default=None, max_length=30)
    unitPrice: float | None = Field(default=None, ge=0)
    totalPrice: float | None = Field(default=None, ge=0)
    evidence: str = Field(min_length=1, max_length=1000)


class InvoiceExtractionRequest(BaseModel):
    documentType: str = Field(pattern="^NFCE$")
    state: str = Field(pattern="^[A-Z]{2}$")
    locale: str = Field(default="pt-BR", max_length=20)
    products: list[InvoiceProductInput] = Field(min_length=1, max_length=500)


class InvoiceItemExtraction(BaseModel):
    lineNumber: int = Field(ge=1)
    description: str = Field(min_length=1, max_length=500)
    productName: str = Field(min_length=1, max_length=255)
    brand: str | None = Field(default=None, max_length=120)
    quantity: float = Field(gt=0)
    unit: str | None = Field(default=None, max_length=30)
    unitOfMeasure: UnitOfMeasure
    unitPrice: float | None = Field(default=None, ge=0)
    totalPrice: float | None = Field(default=None, ge=0)
    category: Category
    storagePlace: StoragePlace
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=1000)


class InvoiceExtraction(BaseModel):
    items: list[InvoiceItemExtraction] = Field(min_length=1, max_length=500)
    warnings: list[str] = Field(default_factory=list, max_length=20)


__all__ = ["InvoiceExtraction", "InvoiceExtractionRequest", "InvoiceItemExtraction", "InvoiceProductInput"]
