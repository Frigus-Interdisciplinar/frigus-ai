-- Integridade de estoque e lista de compras. NÃO aplicada: rodar primeiro as checagens abaixo no banco
-- e tratar o que elas devolverem; depois aplicar e espelhar o resultado em ../schema.sql.

-- Checagem 1: quantidades negativas no estoque (devem ser corrigidas antes da constraint).
-- SELECT id, quantity, minimal_quantity FROM stock_products WHERE quantity < 0 OR minimal_quantity < 0;

-- Checagem 2: estoques com mais de uma lista aberta. Consolidar os itens na lista mais recente
-- (somando quantidade dos produtos repetidos) e marcar as demais como CANCELED antes do índice.
-- SELECT stock_id, count(*) FROM shopping_lists WHERE status = 'OPEN' GROUP BY stock_id HAVING count(*) > 1;

ALTER TABLE stock_products
    ADD CONSTRAINT ck_stock_products_quantity_nonnegative CHECK (quantity >= 0);

ALTER TABLE stock_products
    ADD CONSTRAINT ck_stock_products_minimum_nonnegative CHECK (minimal_quantity IS NULL OR minimal_quantity >= 0);

CREATE UNIQUE INDEX uq_shopping_lists_one_open_per_stock
    ON shopping_lists (stock_id)
    WHERE status = 'OPEN';
