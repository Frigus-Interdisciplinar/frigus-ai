"""
Persistência crua da lista de compras: item pendente/comprado/removido, sempre presa à
lista "Aberta" do estoque do usuário. Sem decisão de negócio nem tradução pra `Response`
— isso fica em `graph/tools/compras/repo.py` (a tool que o LLM chama).

Cada estoque tem no máximo uma lista `Aberta` por vez. `_lista_aberta` cria com `ON CONFLICT DO
NOTHING` e relê: o que garante a unicidade sob concorrência é o índice parcial de
`data/sql/migrations/001_integridade_estoque_compras.sql`.
"""

from datetime import date
from decimal import Decimal
from typing import TypedDict, cast

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from frigus_ai.domain.errors import ItemDeCompraNaoEncontrado, ProdutoNaoCadastrado
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


def _buscar_lista_aberta(s: Session, stock_id: int) -> str | None:
    return s.scalar(
        select(ShoppingList.id)
        .where(ShoppingList.stock_id == stock_id, ShoppingList.status == ABERTA)
        .order_by(ShoppingList.date.desc())
        .limit(1)
    )


def _lista_aberta(s: Session, stock_id: int) -> str:
    if (lista_id := _buscar_lista_aberta(s, stock_id)) is not None:
        return lista_id

    nova_id = s.scalar(
        insert(ShoppingList)
        .values(date=date.today(), stock_id=stock_id, status=ABERTA)
        .on_conflict_do_nothing()
        .returning(ShoppingList.id)
    )
    if nova_id is not None:
        return nova_id

    # Conflito: outra transação criou a lista aberta entre a busca e o insert.
    return cast(str, _buscar_lista_aberta(s, stock_id))


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
    s: Session, stock_id: int, shopping_list_product_id: int | None, product_name: str | None,
    travar: bool = False,
) -> ShoppingListProduct:
    """
    Item por ID direto ou por nome, sempre preso à lista Aberta do estoque do usuário.
    `travar` segura a linha até o fim da transação: sem isso, duas compras simultâneas do
    mesmo item passam as duas pela checagem de `Comprado` e somam o estoque duas vezes.
    """

    stmt = (
        select(ShoppingListProduct)
        .join(ShoppingList, ShoppingList.id == ShoppingListProduct.list_id)
        .where(ShoppingList.stock_id == stock_id, ShoppingList.status == ABERTA)
    )

    if shopping_list_product_id is not None:
        stmt = stmt.where(ShoppingListProduct.id == shopping_list_product_id)
    elif product_name:
        stmt = stmt.join(Product, Product.id == ShoppingListProduct.product_id).where(
            Product.name.icontains(product_name, autoescape=True)
        )
    else:
        raise ItemDeCompraNaoEncontrado

    if travar:
        stmt = stmt.with_for_update(of=ShoppingListProduct)

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
    def registrar_compra(
        self, s: Session, stock_id: int, shopping_list_product_id: int | None, product_name: str | None,
        expire_date: date, product_status: str, quantity: int | None, unit_price: float | None,
    ) -> tuple[int, int]:
        """
        Dá entrada no estoque e marca o item da lista como `Comprado` na mesma transação: sem isso o
        item some da lista mas não aparece no estoque. Mesma validade soma quantidade (igual a
        `estoque_repository.adicionar_produto`). Devolve (id do item do estoque, quantidade final).
        """

        item = _localizar_item(s, stock_id, shopping_list_product_id, product_name, travar=True)
        if item.status == "Comprado":
            raise ValueError("Esse item da lista já foi marcado como comprado; a entrada no estoque já foi feita.")

        produto = s.get(Product, item.product_id)
        comprada = quantity or item.quantity

        # Produto criado pela lista nasce com preço 0 no catálogo; o preço pago preenche, nunca sobrescreve.
        if unit_price and not produto.unit_price:
            produto.unit_price = Decimal(str(unit_price))

        stmt = (
            insert(StockProduct)
            .values(
                product_id=produto.id,
                stock_id=stock_id,
                quantity=comprada,
                expire_date=expire_date,
                product_status=product_status,
                category=produto.category,
            )
            .on_conflict_do_update(
                index_elements=["product_id", "stock_id", "expire_date"],
                set_={"quantity": StockProduct.quantity + comprada},
            )
            .returning(StockProduct.id, StockProduct.quantity)
        )
        stock_product_id, quantidade = s.execute(stmt).one()
        item.status = "Comprado"

        return stock_product_id, quantidade

    @transacional
    def gerar_por_estoque_baixo(self, s: Session, stock_id: int) -> list[ItemCompra]:
        """
        Reconcilia a sugestão com o estoque: repetir a geração mantém a quantidade (não soma de novo)
        e item já comprado ou removido não volta pra `Pendente` sozinho.
        """

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
                    set_={"quantity": sugerida},
                    where=ShoppingListProduct.status == "Pendente",
                )
                .returning(ShoppingListProduct.id, ShoppingListProduct.quantity)
            )
            linha = s.execute(stmt).one_or_none()
            if linha is None:
                continue

            item_id, quantidade_final = linha
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


def registrar_compra(
    stock_id: int, shopping_list_product_id: int | None, product_name: str | None,
    expire_date: date, product_status: str, quantity: int | None, unit_price: float | None,
) -> tuple[int, int]:
    return _compras.registrar_compra(
        stock_id, shopping_list_product_id, product_name, expire_date, product_status, quantity, unit_price
    )


def gerar_por_estoque_baixo(stock_id: int) -> list[ItemCompra]:
    return _compras.gerar_por_estoque_baixo(stock_id)


__all__ = [
    "ItemCompra",
    "adicionar_item",
    "consultar_lista",
    "criar_lista_aberta",
    "gerar_por_estoque_baixo",
    "marcar_status",
    "registrar_compra",
]
