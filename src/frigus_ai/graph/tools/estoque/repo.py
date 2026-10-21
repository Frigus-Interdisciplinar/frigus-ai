from datetime import date

from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.estoque.helpers import (
    compute_product_status,
    expiring_date_threshold,
)
from frigus_ai.graph.tools.estoque.resolver import NomeAmbiguo, resolver_item
from frigus_ai.graph.tools.estoque.schemas import (
    AddStockProductArgs,
    AddStockProductsArgs,
    DiscardProductArgs,
    QueryStockArgs,
    UpdateStockQuantityArgs,
)
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.logging import Logging
from frigus_ai.infra.postgres.context import current_stock_id, current_user_id
from frigus_ai.infra.redis import ranking
from frigus_ai.repositories import estoque_repository
from frigus_ai.repositories.estoque_repository import FiltrosEstoque, ProdutoNovo

logger = Logging.get_logger("pg_estoque")


def _produto_novo(args: AddStockProductArgs) -> ProdutoNovo:
    validade = date.fromisoformat(args.expire_date)

    return ProdutoNovo(
        product_name=args.product_name,
        category=args.category,
        storage_place=args.storage_place,
        quantity=args.quantity,
        minimal_quantity=args.minimal_quantity,
        expire_date=validade,
        product_status=compute_product_status(validade),
        unit_price=args.unit_price,
    )


def _item_pelo_nome(stock_product_id: int | None, product_name: str | None) -> tuple[int | None, str | None]:
    """Com só o nome, resolve pro id (ver `resolver.py`); None no id deixa o repository procurar pelo nome."""

    if stock_product_id is not None or not product_name:
        return stock_product_id, product_name

    resolvido = resolver_item(current_stock_id(), product_name)
    return (resolvido, None) if resolvido is not None else (None, product_name)


class EstoqueRepo(ToolSet):
    def add_stock_product(
        self,
        product_name: str,
        category: str,
        storage_place: str,
        quantity: int,
        expire_date: str,
        unit_price: float = 0.0,
        minimal_quantity: int | None = None,
    ) -> dict:
        """
        Adiciona um produto ao estoque do usuário (geladeira, freezer, despensa, armário ou prateleira).

        Cria o produto no catálogo se ele ainda não existir. Se já houver um item do
        mesmo produto com a MESMA data de validade neste estoque, soma a quantidade
        em vez de criar um novo registro (evita duplicidade).
        """

        dados = _produto_novo(AddStockProductArgs(
            product_name=product_name, category=category, storage_place=storage_place, quantity=quantity,
            expire_date=expire_date, unit_price=unit_price, minimal_quantity=minimal_quantity,
        ))
        item_id, quantidade = estoque_repository.adicionar_produto(current_stock_id(), dados)

        return Response.ok(
            stock_product_id=item_id,
            quantity=quantidade,
            product_status=dados["product_status"],
        )

    def add_stock_products(self, items: list[AddStockProductArgs]) -> dict:
        """
        Adiciona vários produtos ao estoque de uma vez (ex.: os itens reconhecidos numa foto, depois
        que o usuário confirmou). Cada item tem a própria validade. Tudo ou nada: se um item for
        inválido, nenhum é gravado. Mesmo produto com a mesma validade soma quantidade.
        """

        dados = [_produto_novo(AddStockProductArgs.model_validate(item)) for item in items]
        resultados = estoque_repository.adicionar_produtos(current_stock_id(), dados)

        return Response.ok(
            total_adicionados=len(resultados),
            itens=[
                {
                    "stock_product_id": item_id,
                    "product_name": d["product_name"],
                    "quantity": quantidade,
                    "expire_date": str(d["expire_date"]),
                    "product_status": d["product_status"],
                }
                for d, (item_id, quantidade) in zip(dados, resultados, strict=True)
            ],
        )

    def query_stock(
        self,
        storage_place: str | None = None,
        category: str | None = None,
        product_status: str | None = None,
        vencendo_em_dias: int | None = None,
        product_name: str | None = None,
    ) -> dict:
        """
        Consulta os itens do estoque do usuário com filtros opcionais.

        Sempre retorna o semáforo de validade (product_status) de cada item:
        Fresco | Próximo do vencimento | Vencido.
        """

        filtros = FiltrosEstoque(
            storage_place=storage_place,
            category=category,
            product_status=product_status,
            vence_ate=(
                expiring_date_threshold(vencendo_em_dias) if vencendo_em_dias is not None else None
            ),
            product_name=product_name,
        )

        itens = estoque_repository.consultar_estoque(current_stock_id(), filtros)
        return Response.ok(total_records=len(itens), itens=itens)

    def update_stock_quantity(
        self,
        stock_product_id: int | None = None,
        product_name: str | None = None,
        delta: int | None = None,
        novo_valor: int | None = None,
    ) -> dict:
        """
        Atualiza a quantidade de um item do estoque (consumo parcial/total ou reposição).

        Localização por ID direto ou por nome do produto (várias validades do mesmo produto: o item
        mais próximo do vencimento; produtos diferentes parecidos: pergunta qual). Informe `delta` (variação,
        negativo para consumo) OU `novo_valor` (quantidade final), nunca os dois.
        Registra o movimento em stock_movements (Entrada/Saída/Ajuste).
        """

        if delta is None and novo_valor is None:
            return Response.error("Informe 'delta' ou 'novo_valor'.")

        try:
            stock_product_id, product_name = _item_pelo_nome(stock_product_id, product_name)
        except NomeAmbiguo as e:
            return Response.error(str(e))

        item_id, nova_quantidade = estoque_repository.atualizar_quantidade(
            current_stock_id(), current_user_id(),
            stock_product_id, product_name, delta, novo_valor,
        )
        return Response.ok(stock_product_id=item_id, quantity=nova_quantidade)

    def discard_product(
        self,
        stock_product_id: int | None = None,
        product_name: str | None = None,
        reason: str = "Vencido",
    ) -> dict:
        """
        Descarta um item do estoque (produto vencido ou estragado).

        Zera a quantidade do item e grava o descarte em `discard`, usado depois
        pelo agente financeiro para calcular o valor de alimentos desperdiçados.
        """

        try:
            stock_product_id, product_name = _item_pelo_nome(stock_product_id, product_name)
        except NomeAmbiguo as e:
            return Response.error(str(e))

        descarte = estoque_repository.descartar(
            current_stock_id(), current_user_id(), stock_product_id, product_name, reason
        )

        # Estatística do ranking, não a fonte de verdade do desperdício (essa é o Postgres
        # acima, já commitado) — falha no Redis não pode derrubar um descarte que já deu certo.
        try:
            if descarte["quantidade_perdida"] > 0:
                ranking.registrar_descarte(
                    current_stock_id(), descarte["product_name"], descarte["quantidade_perdida"]
                )
        except Exception as e:
            logger.warning("RANKING ERRO | stock_product_id=%s | %s", descarte["stock_product_id"], e)

        return Response.ok(stock_product_id=descarte["stock_product_id"], reason=reason)

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                self.add_stock_product, name="add_stock_product", args_schema=AddStockProductArgs
            ),
            StructuredTool.from_function(
                self.add_stock_products, name="add_stock_products", args_schema=AddStockProductsArgs
            ),
            StructuredTool.from_function(
                self.query_stock, name="query_stock", args_schema=QueryStockArgs
            ),
            StructuredTool.from_function(
                self.update_stock_quantity,
                name="update_stock_quantity",
                args_schema=UpdateStockQuantityArgs,
            ),
            StructuredTool.from_function(
                self.discard_product, name="discard_product", args_schema=DiscardProductArgs
            ),
        ]


__all__ = ["EstoqueRepo"]
