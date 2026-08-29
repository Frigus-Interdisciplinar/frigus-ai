
from langchain.tools import tool

from config.decorators import log_tool
from config.logging import get_logger
from frigus_ai.tools.postgres.compras.schemas import (
    AddShoppingListProductArgs,
    GenerateShoppingListFromLowStockArgs,
    MarkPurchasedArgs,
    QueryShoppingListArgs,
)
from frigus_ai.tools.postgres.connection import get_conn
from frigus_ai.tools.postgres.context import current_stock_id
from frigus_ai.tools.postgres.helpers import next_id
from frigus_ai.tools.response import Response

logger = get_logger("pg_compras")


def _get_or_create_open_list(cur, stock_id: int) -> int:
    cur.execute(
        "SELECT id FROM shopping_lists WHERE stock_id = %s AND status = 'Aberta' ORDER BY date DESC LIMIT 1;",
        (stock_id,)
    )
    row = cur.fetchone()
    if row:
        return row[0]

    list_id = next_id(cur, "shopping_lists")
    cur.execute(
        "INSERT INTO shopping_lists (id, stock_id, status) VALUES (%s, %s, 'Aberta');",
        (list_id, stock_id)
    )
    return list_id


def _find_or_create_product(cur, name: str, category: str | None, storage_place: str | None) -> int | None:
    cur.execute("SELECT id FROM products WHERE LOWER(name) = LOWER(%s) LIMIT 1;", (name,))
    row = cur.fetchone()
    if row:
        return row[0]

    if not category or not storage_place:
        return None

    product_id = next_id(cur, "products")
    cur.execute(
        "INSERT INTO products (id, name, category, storage_place, unit_price) VALUES (%s, %s, %s, %s, 0);",
        (product_id, name, category, storage_place)
    )
    return product_id


@tool("create_shopping_list")
@log_tool
def create_shopping_list() -> dict:
    """
    Garante que exista uma lista de compras aberta para o estoque do usuário,
    criando uma nova se necessário. Retorna o ID da lista aberta.
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                list_id = _get_or_create_open_list(cur, stock_id)
                conn.commit()
                return Response.ok(shopping_list_id=list_id)
            except Exception as e:
                conn.rollback()
                logger.error("CREATE_LIST ERRO | %s", e)
                return Response.error(e)


@tool("add_shopping_list_product", args_schema=AddShoppingListProductArgs)
@log_tool
def add_shopping_list_product(
    product_name: str,
    category: str,
    storage_place: str,
    quantity: int = 1,
) -> dict:
    """
    Adiciona um item à lista de compras aberta do usuário (cria a lista se não existir).

    Se o item já estiver na lista, soma a quantidade em vez de duplicar.
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                list_id = _get_or_create_open_list(cur, stock_id)
                product_id = _find_or_create_product(cur, product_name, category, storage_place)

                if product_id is None:
                    return Response.error("Produto não encontrado no catálogo; informe category e storage_place para cadastrá-lo.")

                new_id = next_id(cur, "shopping_list_products")
                cur.execute(
                    """
                    INSERT INTO shopping_list_products (id, list_id, product_id, status, quantity)
                    VALUES (%s, %s, %s, 'Pendente', %s)
                    ON CONFLICT (list_id, product_id)
                    DO UPDATE SET quantity = shopping_list_products.quantity + EXCLUDED.quantity,
                                  status = 'Pendente'
                    RETURNING id, quantity;
                    """,
                    (new_id, list_id, product_id, quantity)
                )
                final_id, final_quantity = cur.fetchone()
                conn.commit()

                logger.info("ADD_ITEM OK | shopping_list_product_id=%s product=%s quantity=%s", final_id, product_name, final_quantity)

                return Response.ok(shopping_list_product_id=final_id, quantity=final_quantity)

            except Exception as e:
                conn.rollback()
                logger.error("ADD_ITEM ERRO | %s", e)
                return Response.error(e)


@tool("query_shopping_list", args_schema=QueryShoppingListArgs)
@log_tool
def query_shopping_list(status: str | None = None) -> dict:
    """
    Consulta os itens da lista de compras aberta do usuário.

    Sem filtro de status, retorna itens Pendente e Comprado (oculta Removido).
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                query = """
                    SELECT slp.id, p.name, p.category, slp.quantity, slp.status
                    FROM shopping_list_products slp
                    JOIN shopping_lists sl ON sl.id = slp.list_id
                    JOIN products p ON p.id = slp.product_id
                    WHERE sl.stock_id = %s AND sl.status = 'Aberta'
                """
                params: list = [stock_id]

                if status:
                    query += " AND slp.status = %s"
                    params.append(status)
                else:
                    query += " AND slp.status != 'Removido'"

                cur.execute(query, params)
                rows = cur.fetchall()

                itens = [
                    {
                        "shopping_list_product_id": row[0],
                        "product_name":             row[1],
                        "category":                 row[2],
                        "quantity":                 row[3],
                        "status":                   row[4],
                    }
                    for row in rows
                ]

                logger.info("QUERY OK | query_shopping_list | total=%s", len(itens))

                return Response.ok(total_records=len(itens), itens=itens)

            except Exception as e:
                logger.error("QUERY ERRO | query_shopping_list | %s", e)
                return Response.error(e)


@tool("mark_purchased", args_schema=MarkPurchasedArgs)
@log_tool
def mark_purchased(
    shopping_list_product_id: int | None = None,
    product_name: str | None = None,
    status: str = "Comprado",
) -> dict:
    """
    Marca um item da lista de compras como Comprado ou Removido.

    Localização por ID direto ou por nome do produto na lista aberta do usuário.
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                target_id = shopping_list_product_id

                if target_id is None:
                    if not product_name:
                        return Response.error("Informe shopping_list_product_id ou product_name.")

                    cur.execute(
                        """
                        SELECT slp.id
                        FROM shopping_list_products slp
                        JOIN shopping_lists sl ON sl.id = slp.list_id
                        JOIN products p ON p.id = slp.product_id
                        WHERE sl.stock_id = %s AND sl.status = 'Aberta' AND p.name ILIKE %s
                        LIMIT 1;
                        """,
                        (stock_id, f"%{product_name}%")
                    )
                    row = cur.fetchone()
                    if not row:
                        return Response.error("Item não encontrado na lista de compras aberta.")
                    target_id = row[0]

                # O EXISTS impede que um shopping_list_product_id vindo do LLM
                # altere item de outra lista/estoque — o caminho por product_name
                # já filtra por stock_id, o caminho por ID não filtrava nada.
                cur.execute(
                    """
                    UPDATE shopping_list_products slp
                    SET status = %s
                    WHERE slp.id = %s
                      AND EXISTS (
                          SELECT 1 FROM shopping_lists sl
                          WHERE sl.id = slp.list_id
                            AND sl.stock_id = %s
                            AND sl.status = 'Aberta'
                      );
                    """,
                    (status, target_id, stock_id)
                )

                if cur.rowcount == 0:
                    conn.rollback()
                    return Response.error("Item não encontrado na lista de compras aberta.")

                conn.commit()

                logger.info("MARK OK | shopping_list_product_id=%s status=%s", target_id, status)

                return Response.ok(shopping_list_product_id=target_id, status=status)

            except Exception as e:
                conn.rollback()
                logger.error("MARK ERRO | %s", e)
                return Response.error(e)


@tool("generate_shopping_list_from_low_stock", args_schema=GenerateShoppingListFromLowStockArgs)
@log_tool
def generate_shopping_list_from_low_stock() -> dict:
    """
    Gera/atualiza a lista de compras com base em itens do estoque abaixo da
    quantidade mínima configurada (minimal_quantity em stock_products).
    """

    stock_id = current_stock_id()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT p.id, p.name, p.category, sp.quantity, sp.minimal_quantity
                    FROM stock_products sp
                    JOIN products p ON p.id = sp.product_id
                    WHERE sp.stock_id = %s
                      AND sp.minimal_quantity IS NOT NULL
                      AND sp.quantity <= sp.minimal_quantity;
                    """,
                    (stock_id,)
                )
                baixos = cur.fetchall()

                if not baixos:
                    return Response.ok(total_adicionados=0, itens=[])

                list_id = _get_or_create_open_list(cur, stock_id)
                adicionados = []

                for product_id, name, category, quantidade, minimo in baixos:
                    sugerida = max(minimo - quantidade, 1)
                    new_id = next_id(cur, "shopping_list_products")
                    cur.execute(
                        """
                        INSERT INTO shopping_list_products (id, list_id, product_id, status, quantity)
                        VALUES (%s, %s, %s, 'Pendente', %s)
                        ON CONFLICT (list_id, product_id)
                        DO UPDATE SET quantity = shopping_list_products.quantity + EXCLUDED.quantity
                        RETURNING id, quantity;
                        """,
                        (new_id, list_id, product_id, sugerida)
                    )
                    item_id, quantidade_final = cur.fetchone()
                    adicionados.append({
                        "shopping_list_product_id": item_id,
                        "product_name": name,
                        "category": category,
                        "quantity": quantidade_final,
                    })

                conn.commit()

                logger.info("GENERATE OK | total_adicionados=%s", len(adicionados))

                return Response.ok(total_adicionados=len(adicionados), itens=adicionados)

            except Exception as e:
                conn.rollback()
                logger.error("GENERATE ERRO | %s", e)
                return Response.error(e)


__all__ = [
    "add_shopping_list_product",
    "create_shopping_list",
    "generate_shopping_list_from_low_stock",
    "mark_purchased",
    "query_shopping_list",
]
