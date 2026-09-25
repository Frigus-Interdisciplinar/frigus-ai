"""
Persistência crua da lista de compras: item pendente/comprado/removido, sempre presa à
lista "Aberta" do estoque do usuário. Sem decisão de negócio nem tradução pra `Response`
— isso fica em `graph/tools/compras/repo.py` (a tool que o LLM chama).

Cada estoque tem no máximo uma lista `Aberta` por vez — `_lista_aberta` garante isso
(busca antes de criar), igual `_get_or_create_open_list` fazia no SQL cru.
"""

from datetime import date
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from frigus_ai.exceptions import ItemDeCompraNaoEncontrado, ProdutoNaoCadastrado
from frigus_ai.infra.postgres.connection import PostgresRepo, transacional
from frigus_ai.infra.postgres.models import (
    Product,
    ShoppingList,
    ShoppingListProduct,
    StockProduct,
)

ABERTA = "Aberta"


class ItemCompra(TypedDict):
    shopping_list_product_id: int
    product_name: str
    category: str
    quantity: int
    status: str | None


def _lista_aberta(s: Session, stock_id: int) -> str:
    lista_id = s.scalar(
        select(ShoppingList.id)
        .where(ShoppingList.stock_id == stock_id, ShoppingList.status == ABERTA)
        .order_by(ShoppingList.date.desc())
        .limit(1)
    )
    if lista_id is not None:
        return lista_id

    nova = ShoppingList(date=date.today(), stock_id=stock_id, status=ABERTA)
    s.add(nova)
    s.flush()

    return nova.id


def _produto_do_catalogo(s: Session, name: str, category: str | None, storage_place: str | None) -> int:
    existente = s.scalar(select(Product.id).where(func.lower(Product.name) == name.lower()).limit(1))
    if existente is not None:
        return existente

    if not category or not storage_place:
        raise ProdutoNaoCadastrado

    novo = Product(name=name, category=category, storage_place=storage_place, unit_price=0)
    s.add(novo)
    s.flush()

    return novo.id


def _localizar_item(
    s: Session, stock_id: int, shopping_list_product_id: int | None, product_name: str | None
) -> ShoppingListProduct:
    """Item por ID direto ou por nome, sempre preso à lista Aberta do estoque do usuário."""

    stmt = (
        select(ShoppingListProduct)
        .join(ShoppingList, ShoppingList.id == ShoppingListProduct.list_id)
        .where(ShoppingList.stock_id == stock_id, ShoppingList.status == ABERTA)
    )

    if shopping_list_product_id is not None:
        stmt = stmt.where(ShoppingListProduct.id == shopping_list_product_id)
    elif product_name:
        stmt = stmt.join(Product, Product.id == ShoppingListProduct.product_id).where(
            Product.name.ilike(f"%{product_name}%")
        )
    else:
        raise ItemDeCompraNaoEncontrado

    item = s.scalars(stmt.limit(1)).first()
    if item is None:
        raise ItemDeCompraNaoEncontrado

    return item


class _ComprasPostgresRepo(PostgresRepo):
    @transacional
    def criar_lista_aberta(self, s: Session, stock_id: int) -> str:
        return _lista_aberta(s, stock_id)

    @transacional
    def adicionar_item(
        self, s: Session, stock_id: int, product_name: str, category: str | None,
        storage_place: str | None, quantity: int,
    ) -> tuple[int, int]:
        """Soma quantidade se o item já estiver na lista, em vez de duplicar."""

        lista_id = _lista_aberta(s, stock_id)
        product_id = _produto_do_catalogo(s, product_name, category, storage_place)

        stmt = (
            insert(ShoppingListProduct)
            .values(
                list_id=lista_id,
                product_id=product_id,
                status="Pendente",
                quantity=quantity,
            )
            .on_conflict_do_update(
                index_elements=["list_id", "product_id"],
                set_={"quantity": ShoppingListProduct.quantity + quantity, "status": "Pendente"},
            )
            .returning(ShoppingListProduct.id, ShoppingListProduct.quantity)
        )

        return s.execute(stmt).one()

    @transacional
    def consultar_lista(self, s: Session, stock_id: int, status: str | None) -> list[ItemCompra]:
        stmt = (
            select(
                ShoppingListProduct.id, Product.name, Product.category,
                ShoppingListProduct.quantity, ShoppingListProduct.status,
            )
            .join(ShoppingList, ShoppingList.id == ShoppingListProduct.list_id)
            .join(Product, Product.id == ShoppingListProduct.product_id)
            .where(ShoppingList.stock_id == stock_id, ShoppingList.status == ABERTA)
        )

        stmt = stmt.where(ShoppingListProduct.status == status) if status else stmt.where(
            ShoppingListProduct.status != "Removido"
        )

        return [
            {"shopping_list_product_id": item_id, "product_name": nome, "category": categoria,
             "quantity": quantidade, "status": item_status}
            for item_id, nome, categoria, quantidade, item_status in s.execute(stmt)
        ]

    @transacional
    def marcar_status(
        self, s: Session, stock_id: int, shopping_list_product_id: int | None,
        product_name: str | None, status: str,
    ) -> int:
        item = _localizar_item(s, stock_id, shopping_list_product_id, product_name)
        item.status = status

        return item.id

    @transacional
    def gerar_por_estoque_baixo(self, s: Session, stock_id: int) -> list[ItemCompra]:
        baixos = s.execute(
            select(
                StockProduct.product_id, 
                Product.name, 
                Product.category,
                StockProduct.quantity, 
                StockProduct.minimal_quantity,
            )
            .join(Product, Product.id == StockProduct.product_id)
            .where(
                StockProduct.stock_id == stock_id,
                StockProduct.minimal_quantity.is_not(None),
                StockProduct.quantity <= StockProduct.minimal_quantity,
            )
        ).all()

        if not baixos:
            return []

        lista_id = _lista_aberta(s, stock_id)
        adicionados: list[ItemCompra] = []

        for product_id, name, category, quantidade, minimo in baixos:
            sugerida = max(minimo - quantidade, 1)
            stmt = (
                insert(ShoppingListProduct)
                .values(
                        list_id=lista_id,
                    product_id=product_id,
                    status="Pendente",
                    quantity=sugerida,
                )
                .on_conflict_do_update(
                    index_elements=["list_id", "product_id"],
                    set_={"quantity": ShoppingListProduct.quantity + sugerida},
                )
                .returning(ShoppingListProduct.id, ShoppingListProduct.quantity)
            )
            item_id, quantidade_final = s.execute(stmt).one()
            adicionados.append({
                "shopping_list_product_id": item_id, "product_name": name,
                "category": category, "quantity": quantidade_final, "status": "Pendente",
            })

        return adicionados


_compras = _ComprasPostgresRepo()


def criar_lista_aberta(stock_id: int) -> str:
    return _compras.criar_lista_aberta(stock_id)


def adicionar_item(
    stock_id: int, product_name: str, category: str | None, storage_place: str | None, quantity: int
) -> tuple[int, int]:
    return _compras.adicionar_item(stock_id, product_name, category, storage_place, quantity)


def consultar_lista(stock_id: int, status: str | None) -> list[ItemCompra]:
    return _compras.consultar_lista(stock_id, status)


def marcar_status(
    stock_id: int, shopping_list_product_id: int | None, product_name: str | None, status: str
) -> int:
    return _compras.marcar_status(stock_id, shopping_list_product_id, product_name, status)


def gerar_por_estoque_baixo(stock_id: int) -> list[ItemCompra]:
    return _compras.gerar_por_estoque_baixo(stock_id)


__all__ = [
    "ItemCompra",
    "adicionar_item",
    "consultar_lista",
    "criar_lista_aberta",
    "gerar_por_estoque_baixo",
    "marcar_status",
]
