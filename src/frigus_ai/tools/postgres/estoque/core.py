from datetime import date
from typing import Optional
from langchain.tools import tool

from config.decorators import log_tool
from config.logging import get_logger

from frigus_ai.tools.response import Response
from frigus_ai.tools.postgres.connection import get_conn
from frigus_ai.tools.postgres.context import current_stock_id, current_user_id
from frigus_ai.tools.postgres.helpers import (
    next_id,
    compute_product_status,
    expiring_date_threshold,
)
from frigus_ai.tools.postgres.estoque.schemas import (
    AddStockProductArgs,
    QueryStockArgs,
    UpdateStockQuantityArgs,
    DiscardProductArgs,
)

logger = get_logger("pg_estoque")


def _find_or_create_product(cur, name: str, category: str, storage_place: str, unit_price: float) -> int:
    cur.execute(
        "SELECT id FROM products WHERE LOWER(name) = LOWER(%s) LIMIT 1;",
        (name,)
    )
    row = cur.fetchone()
    if row:
        return row[0]

    product_id = next_id(cur, "products")
    cur.execute(
        """
        INSERT INTO products (id, name, category, storage_place, unit_price)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (product_id, name, category, storage_place, unit_price)
    )
    return product_id


def _find_stock_product(cur, stock_id: int, stock_product_id: Optional[int], product_name: Optional[str]):
    if stock_product_id is not None:
        cur.execute(
            """
            SELECT sp.id, sp.quantity, sp.product_id
            FROM stock_products sp
            WHERE sp.id = %s AND sp.stock_id = %s;
            """,
            (stock_product_id, stock_id)
        )
        return cur.fetchone()

    if not product_name:
        return None

    cur.execute(
        """
        SELECT sp.id, sp.quantity, sp.product_id
        FROM stock_products sp
        JOIN products p ON p.id = sp.product_id
        WHERE sp.stock_id = %s AND p.name ILIKE %s
        ORDER BY sp.expire_date ASC
        LIMIT 1;
        """,
        (stock_id, f"%{product_name}%")
    )
    return cur.fetchone()


@tool("add_stock_product", args_schema=AddStockProductArgs)
@log_tool
def add_stock_product(
    product_name: str,
    category: str,
    storage_place: str,
    quantity: int,
    expire_date: str,
    unit_price: float = 0.0,
    minimal_quantity: Optional[int] = None,
) -> dict:
    """
    Adiciona um produto ao estoque do usuário (geladeira, freezer, despensa, armário ou prateleira).

    Cria o produto no catálogo se ele ainda não existir. Se já houver um item do
    mesmo produto com a MESMA data de validade neste estoque, soma a quantidade
    em vez de criar um novo registro (evita duplicidade).
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                product_id = _find_or_create_product(cur, product_name, category, storage_place, unit_price)
                status = compute_product_status(date.fromisoformat(expire_date))

                new_id = next_id(cur, "stock_products")
                cur.execute(
                    """
                    INSERT INTO stock_products
                        (id, product_id, stock_id, quantity, minimal_quantity, expire_date, product_status, category)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (product_id, stock_id, expire_date)
                    DO UPDATE SET quantity = stock_products.quantity + EXCLUDED.quantity
                    RETURNING id, quantity;
                    """,
                    (new_id, product_id, stock_id, quantity, minimal_quantity, expire_date, status, category)
                )
                final_id, final_quantity = cur.fetchone()
                conn.commit()

                logger.info("INSERT OK | stock_product_id=%s product=%s quantity=%s", final_id, product_name, final_quantity)

                return Response.ok(stock_product_id=final_id, quantity=final_quantity, product_status=status)

            except Exception as e:
                conn.rollback()
                logger.error("INSERT ERRO | %s", e)
                return Response.error(e)


@tool("query_stock", args_schema=QueryStockArgs)
@log_tool
def query_stock(
    storage_place: Optional[str] = None,
    category: Optional[str] = None,
    product_status: Optional[str] = None,
    vencendo_em_dias: Optional[int] = None,
    product_name: Optional[str] = None,
) -> dict:
    """
    Consulta os itens do estoque do usuário com filtros opcionais.

    Sempre retorna o semáforo de validade (product_status) de cada item:
    Fresco | Próximo do vencimento | Vencido.
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                query = """
                    SELECT sp.id, p.name, sp.category, p.storage_place, sp.quantity,
                           sp.minimal_quantity, sp.expire_date, sp.product_status, p.unit_price
                    FROM stock_products sp
                    JOIN products p ON p.id = sp.product_id
                    WHERE sp.stock_id = %s
                """
                params: list = [stock_id]

                if storage_place:
                    query += " AND p.storage_place = %s"
                    params.append(storage_place)

                if category:
                    query += " AND sp.category = %s"
                    params.append(category)

                if product_status:
                    query += " AND sp.product_status = %s"
                    params.append(product_status)

                if vencendo_em_dias is not None:
                    query += " AND sp.expire_date <= %s"
                    params.append(expiring_date_threshold(vencendo_em_dias))

                if product_name:
                    query += " AND p.name ILIKE %s"
                    params.append(f"%{product_name}%")

                query += " ORDER BY sp.expire_date ASC"

                cur.execute(query, params)
                rows = cur.fetchall()

                itens = [
                    {
                        "stock_product_id": row[0],
                        "product_name":     row[1],
                        "category":         row[2],
                        "storage_place":    row[3],
                        "quantity":         row[4],
                        "minimal_quantity": row[5],
                        "expire_date":      str(row[6]),
                        "product_status":   row[7],
                        "unit_price":       float(row[8]),
                    }
                    for row in rows
                ]

                logger.info("QUERY OK | query_stock | total=%s", len(itens))

                return Response.ok(total_records=len(itens), itens=itens)

            except Exception as e:
                logger.error("QUERY ERRO | query_stock | %s", e)
                return Response.error(e)


@tool("update_stock_quantity", args_schema=UpdateStockQuantityArgs)
@log_tool
def update_stock_quantity(
    stock_product_id: Optional[int] = None,
    product_name: Optional[str] = None,
    delta: Optional[int] = None,
    novo_valor: Optional[int] = None,
) -> dict:
    """
    Atualiza a quantidade de um item do estoque (consumo parcial/total ou reposição).

    Localização por ID direto ou por nome do produto (usa o item mais próximo do
    vencimento em caso de múltiplas ocorrências). Informe `delta` (variação,
    negativo para consumo) OU `novo_valor` (quantidade final), nunca os dois.
    Registra o movimento em stock_movements (Entrada/Saída/Ajuste).
    """

    if delta is None and novo_valor is None:
        return Response.error("Informe 'delta' ou 'novo_valor'.")

    stock_id = current_stock_id()
    user_id = current_user_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                found = _find_stock_product(cur, stock_id, stock_product_id, product_name)
                if not found:
                    return Response.error("Nenhum item de estoque encontrado para os filtros fornecidos.")

                target_id, quantidade_atual, _product_id = found

                if novo_valor is not None:
                    nova_quantidade = novo_valor
                    variacao = nova_quantidade - quantidade_atual
                    movement_type = "Ajuste"
                else:
                    variacao = delta
                    nova_quantidade = quantidade_atual + delta
                    movement_type = "Entrada" if delta > 0 else "Saída"

                if nova_quantidade < 0:
                    return Response.error("Quantidade final não pode ser negativa.")

                cur.execute(
                    "UPDATE stock_products SET quantity = %s WHERE id = %s;",
                    (nova_quantidade, target_id)
                )

                movement_id = next_id(cur, "stock_movements")
                cur.execute(
                    """
                    INSERT INTO stock_movements (id, stock_product_id, user_id, movement_type, quantity)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (movement_id, target_id, user_id, movement_type, abs(variacao))
                )

                conn.commit()

                logger.info("UPDATE OK | stock_product_id=%s nova_quantidade=%s", target_id, nova_quantidade)

                return Response.ok(stock_product_id=target_id, quantity=nova_quantidade)

            except Exception as e:
                conn.rollback()
                logger.error("UPDATE ERRO | stock_product_id=%s | %s", stock_product_id, e)
                return Response.error(e)


@tool("discard_product", args_schema=DiscardProductArgs)
@log_tool
def discard_product(
    stock_product_id: Optional[int] = None,
    product_name: Optional[str] = None,
    reason: str = "Vencido",
) -> dict:
    """
    Descarta um item do estoque (produto vencido ou estragado).

    Zera a quantidade do item e grava o descarte em `discard`, usado depois
    pelo agente financeiro para calcular o valor de alimentos desperdiçados.
    """

    stock_id = current_stock_id()
    user_id = current_user_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                found = _find_stock_product(cur, stock_id, stock_product_id, product_name)
                if not found:
                    return Response.error("Nenhum item de estoque encontrado para os filtros fornecidos.")

                target_id, quantidade_atual, _product_id = found

                # discard não tem coluna de quantidade — gravamos o volume perdido em
                # stock_movements (mesma transação, mesmo CURRENT_TIMESTAMP) para o
                # agente financeiro conseguir calcular o valor descartado depois.
                discard_id = next_id(cur, "discard")
                cur.execute(
                    "INSERT INTO discard (id, stock_product_id, reason) VALUES (%s, %s, %s) RETURNING date;",
                    (discard_id, target_id, reason)
                )
                discard_date = cur.fetchone()[0]

                if quantidade_atual > 0:
                    movement_id = next_id(cur, "stock_movements")
                    cur.execute(
                        """
                        INSERT INTO stock_movements (id, stock_product_id, user_id, movement_type, quantity, date)
                        VALUES (%s, %s, %s, 'Saída', %s, %s);
                        """,
                        (movement_id, target_id, user_id, quantidade_atual, discard_date)
                    )

                cur.execute(
                    "UPDATE stock_products SET quantity = 0, product_status = 'Vencido' WHERE id = %s;",
                    (target_id,)
                )

                conn.commit()

                logger.info("DISCARD OK | stock_product_id=%s reason=%s", target_id, reason)

                return Response.ok(stock_product_id=target_id, reason=reason)

            except Exception as e:
                conn.rollback()
                logger.error("DISCARD ERRO | stock_product_id=%s | %s", stock_product_id, e)
                return Response.error(e)


__all__ = [
    "add_stock_product",
    "query_stock",
    "update_stock_quantity",
    "discard_product",
]
