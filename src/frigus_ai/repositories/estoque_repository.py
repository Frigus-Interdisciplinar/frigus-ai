"""Persistência crua do estoque (catálogo, itens, movimentações, descartes), sem regra de negócio.

Cada método público é uma unidade de trabalho sob `@transacional`: localizar e alterar o item
ficam na mesma transação pra não abrir janela entre ler a quantidade e gravar a nova.
A tool que o LLM chama é `graph/tools/estoque/repo.py`.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import NotRequired, TypedDict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from frigus_ai.domain.errors import ItemDeEstoqueNaoEncontrado, QuantidadeNegativa
from frigus_ai.infra.postgres.connection import PostgresRepo, transacional
from frigus_ai.infra.postgres.models import (
    AJUSTE,
    ENTRADA,
    SAIDA,
    VENCIDO,
    Discard,
    Product,
    StockMovement,
    StockProduct,
)


class ProdutoNovo(TypedDict):
    """Dados que a tool já normalizou (enums resolvidos, status calculado)."""

    product_name:     str
    category:         str
    storage_place:    str
    quantity:         int
    minimal_quantity: int | None
    expire_date:      date
    product_status:   str
    unit_price:       float


class ItemEstoque(TypedDict):
    stock_product_id: int
    product_name:     str
    category:         str
    storage_place:    str
    quantity:         int
    minimal_quantity: int | None
    expire_date:      str
    product_status:   str | None
    unit_price:       float


class DescarteInfo(TypedDict):
    stock_product_id: int
    product_name: str
    quantidade_perdida: int


class FiltrosEstoque(TypedDict):
    storage_place:  NotRequired[str | None]
    category:       NotRequired[str | None]
    product_status: NotRequired[str | None]
    vence_ate:      NotRequired[date | None]
    product_name:   NotRequired[str | None]


def _localizar(
    s: Session, stock_id: int, stock_product_id: int | None, product_name: str | None
) -> StockProduct:
    """Item por ID ou pelo nome do produto (o mais próximo do vencimento), sempre preso ao `stock_id`."""

    stmt = select(StockProduct).where(StockProduct.stock_id == stock_id)

    if stock_product_id is not None:
        stmt = stmt.where(StockProduct.id == stock_product_id)
    elif product_name:
        stmt = (
            stmt.join(Product, Product.id == StockProduct.product_id)
            .where(Product.name.icontains(product_name, autoescape=True))
            .order_by(StockProduct.expire_date.asc())
        )
    else:
        raise ItemDeEstoqueNaoEncontrado

    item = s.scalars(stmt.limit(1)).first()
    if item is None:
        raise ItemDeEstoqueNaoEncontrado

    return item


def _registrar_movimento(
    s: Session,
    stock_product_id: int,
    user_id: str,
    movement_type: str,
    quantidade: int,
    quando: datetime | None = None,
) -> None:
    movimento = StockMovement(
        stock_product_id=stock_product_id,
        user_id=user_id,
        movement_type=movement_type,
        quantity=quantidade,
    )
    if quando is not None:  # sem data: omite a coluna e vale o DEFAULT do banco (None viraria NULL)
        movimento.date = quando
    s.add(movimento)


def _produto_do_catalogo(s: Session, dados: ProdutoNovo) -> int:
    """Reaproveita o produto existente (case-insensitive) ou cria um novo no catálogo."""

    existente = s.scalar(
        select(Product.id)
        .where(func.lower(Product.name) == dados["product_name"].lower())
        .limit(1)
    )
    if existente is not None:
        return existente

    novo = Product(
        name=dados["product_name"],
        category=dados["category"],
        storage_place=dados["storage_place"],
        unit_price=Decimal(str(dados["unit_price"])),
    )
    s.add(novo)
    s.flush()  # o id precisa existir pro insert do StockProduct na mesma transação

    return novo.id


class _EstoquePostgresRepo(PostgresRepo):
    @transacional
    def adicionar_produto(self, s: Session, stock_id: int, dados: ProdutoNovo) -> tuple[int, int]:
        """Cria o produto se não existir e insere o item; mesma validade soma quantidade (ON CONFLICT)."""

        product_id = _produto_do_catalogo(s, dados)

        stmt = (
            insert(StockProduct)
            .values(
                product_id=product_id,
                stock_id=stock_id,
                quantity=dados["quantity"],
                minimal_quantity=dados["minimal_quantity"],
                expire_date=dados["expire_date"],
                product_status=dados["product_status"],
                category=dados["category"],
            )
            .on_conflict_do_update(
                index_elements=["product_id", "stock_id", "expire_date"],
                set_={"quantity": StockProduct.quantity + dados["quantity"]},
            )
            .returning(StockProduct.id, StockProduct.quantity)
        )

        item_id, quantidade = s.execute(stmt).one()

        return item_id, quantidade

    @transacional
    def consultar_estoque(
        self, s: Session, stock_id: int, filtros: FiltrosEstoque
    ) -> list[ItemEstoque]:
        stmt = (
            select(
                StockProduct.id, Product.name, StockProduct.category, Product.storage_place,
                StockProduct.quantity, StockProduct.minimal_quantity, StockProduct.expire_date,
                StockProduct.product_status, Product.unit_price,
            )
            .join(Product, Product.id == StockProduct.product_id)
            .where(StockProduct.stock_id == stock_id)
        )

        # Cada filtro é opcional e se acumula — equivalente ao `query += " AND ..."` do SQL cru.
        iguais = {
            Product.storage_place:       filtros.get("storage_place"),
            StockProduct.category:       filtros.get("category"),
            StockProduct.product_status: filtros.get("product_status"),
        }
        for coluna, valor in iguais.items():
            if valor:
                stmt = stmt.where(coluna == valor)

        if (vence_ate := filtros.get("vence_ate")) is not None:
            stmt = stmt.where(StockProduct.expire_date <= vence_ate)

        if nome := filtros.get("product_name"):
            stmt = stmt.where(Product.name.icontains(nome, autoescape=True))

        stmt = stmt.order_by(StockProduct.expire_date.asc())

        return [
            {
                "stock_product_id": item_id,
                "product_name":     nome_produto,
                "category":         categoria,
                "storage_place":    local,
                "quantity":         quantidade,
                "minimal_quantity": minima,
                "expire_date":      str(validade),
                "product_status":   status,
                "unit_price":       float(preco),
            }
            for item_id, nome_produto, categoria, local, quantidade, minima, validade, status, preco
            in s.execute(stmt)
        ]

    @transacional
    def atualizar_quantidade(
        self,
        s: Session,
        stock_id: int,
        user_id: str,
        stock_product_id: int | None,
        product_name: str | None,
        delta: int | None,
        novo_valor: int | None,
    ) -> tuple[int, int]:
        """
        Localiza, recalcula e grava o movimento numa transação só. A trigger
        `trg_stock_movements_apply` do Supabase aplica a variação em `quantity` (o app NÃO mexe).
        `novo_valor` vira `Ajuste`; `delta` vira `Entrada`/`Saída`. Devolve (id do item, quantidade final).
        """

        item = _localizar(s, stock_id, stock_product_id, product_name)

        if novo_valor is not None:
            nova_quantidade = novo_valor
            variacao = nova_quantidade - item.quantity
            movement_type = AJUSTE
        elif delta is not None:
            variacao = delta
            nova_quantidade = item.quantity + delta
            movement_type = ENTRADA if delta > 0 else SAIDA
        else:
            raise QuantidadeNegativa

        if nova_quantidade < 0:
            raise QuantidadeNegativa

        quantidade_movimento = variacao if movement_type == AJUSTE else abs(variacao)
        _registrar_movimento(s, item.id, user_id, movement_type, quantidade_movimento)

        return item.id, nova_quantidade

    @transacional
    def descartar(
        self,
        s: Session,
        stock_id: int,
        user_id: str,
        stock_product_id: int | None,
        product_name: str | None,
        reason: str,
    ) -> DescarteInfo:
        """
        Grava o descarte e uma `Saída` do volume inteiro (a trigger zera o item), com a MESMA data:
        o financeiro casa descarte e movimento por (stock_product_id, date). Devolve também nome e
        quantidade perdidos, que alimentam o ranking de desperdício no Redis.
        """

        item = _localizar(s, stock_id, stock_product_id, product_name)
        nome_produto = s.scalar(select(Product.name).where(Product.id == item.product_id))
        quantidade_perdida = item.quantity

        descarte = Discard(stock_product_id=item.id, reason=reason)
        s.add(descarte)
        s.flush()          # o DEFAULT do banco preenche `date`...
        s.refresh(descarte)  # ...e o refresh traz o valor pro objeto

        if quantidade_perdida > 0:
            _registrar_movimento(s, item.id, user_id, SAIDA, quantidade_perdida, descarte.date)

        item.product_status = VENCIDO

        return DescarteInfo(
            stock_product_id=item.id, product_name=nome_produto, quantidade_perdida=quantidade_perdida
        )


_estoque = _EstoquePostgresRepo()


def adicionar_produto(stock_id: int, dados: ProdutoNovo) -> tuple[int, int]:
    return _estoque.adicionar_produto(stock_id, dados)


def consultar_estoque(stock_id: int, filtros: FiltrosEstoque) -> list[ItemEstoque]:
    return _estoque.consultar_estoque(stock_id, filtros)


def atualizar_quantidade(
    stock_id: int,
    user_id: str,
    stock_product_id: int | None,
    product_name: str | None,
    delta: int | None,
    novo_valor: int | None,
) -> tuple[int, int]:
    return _estoque.atualizar_quantidade(
        stock_id, user_id, stock_product_id, product_name, delta, novo_valor
    )


def descartar(
    stock_id: int,
    user_id: str,
    stock_product_id: int | None,
    product_name: str | None,
    reason: str,
) -> DescarteInfo:
    return _estoque.descartar(stock_id, user_id, stock_product_id, product_name, reason)


__all__ = [
    "DescarteInfo",
    "FiltrosEstoque",
    "ItemEstoque",
    "ProdutoNovo",
    "adicionar_produto",
    "atualizar_quantidade",
    "consultar_estoque",
    "descartar",
]
