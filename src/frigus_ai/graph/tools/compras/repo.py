from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.compras.schemas import (
    AddShoppingListProductArgs,
    GenerateShoppingListFromLowStockArgs,
    MarkPurchasedArgs,
    QueryShoppingListArgs,
)
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.postgres.context import current_stock_id
from frigus_ai.logging import Logging
from frigus_ai.repositories import compras_repository

logger = Logging.get_logger("pg_compras")


class ComprasRepo(ToolSet):
    @Logging.log_tool
    def create_shopping_list(self) -> dict:
        """
        Garante que exista uma lista de compras aberta para o estoque do usuário,
        criando uma nova se necessário. Retorna o ID da lista aberta.
        """

        try:
            list_id = compras_repository.criar_lista_aberta(current_stock_id())
        except Exception as e:
            logger.error("CREATE_LIST ERRO | %s", e)
            return Response.error(e)

        return Response.ok(shopping_list_id=list_id)

    @Logging.log_tool
    def add_shopping_list_product(
        self,
        product_name: str,
        category: str,
        storage_place: str,
        quantity: int = 1,
    ) -> dict:
        """
        Adiciona um item à lista de compras aberta do usuário (cria a lista se não existir).

        Se o item já estiver na lista, soma a quantidade em vez de duplicar.
        """

        try:
            final_id, final_quantity = compras_repository.adicionar_item(
                current_stock_id(), product_name, category, storage_place, quantity
            )
        except Exception as e:
            logger.error("ADD_ITEM ERRO | %s", e)
            return Response.error(e)

        logger.info(
            "ADD_ITEM OK | shopping_list_product_id=%s product=%s quantity=%s",
            final_id, product_name, final_quantity,
        )

        return Response.ok(shopping_list_product_id=final_id, quantity=final_quantity)

    @Logging.log_tool
    def query_shopping_list(self, status: str | None = None) -> dict:
        """
        Consulta os itens da lista de compras aberta do usuário.

        Sem filtro de status, retorna itens Pendente e Comprado (oculta Removido).
        """

        try:
            itens = compras_repository.consultar_lista(current_stock_id(), status)
        except Exception as e:
            logger.error("QUERY ERRO | query_shopping_list | %s", e)
            return Response.error(e)

        logger.info("QUERY OK | query_shopping_list | total=%s", len(itens))

        return Response.ok(total_records=len(itens), itens=itens)

    @Logging.log_tool
    def mark_purchased(
        self,
        shopping_list_product_id: int | None = None,
        product_name: str | None = None,
        status: str = "Comprado",
    ) -> dict:
        """
        Marca um item da lista de compras como Comprado ou Removido.

        Localização por ID direto ou por nome do produto na lista aberta do usuário.
        """

        if shopping_list_product_id is None and not product_name:
            return Response.error("Informe shopping_list_product_id ou product_name.")

        try:
            target_id = compras_repository.marcar_status(
                current_stock_id(), shopping_list_product_id, product_name, status
            )
        except Exception as e:
            logger.error("MARK ERRO | %s", e)
            return Response.error(e)

        logger.info("MARK OK | shopping_list_product_id=%s status=%s", target_id, status)

        return Response.ok(shopping_list_product_id=target_id, status=status)

    @Logging.log_tool
    def generate_shopping_list_from_low_stock(self) -> dict:
        """
        Gera/atualiza a lista de compras com base em itens do estoque abaixo da
        quantidade mínima configurada (minimal_quantity em stock_products).
        """

        try:
            adicionados = compras_repository.gerar_por_estoque_baixo(current_stock_id())
        except Exception as e:
            logger.error("GENERATE ERRO | %s", e)
            return Response.error(e)

        logger.info("GENERATE OK | total_adicionados=%s", len(adicionados))

        return Response.ok(total_adicionados=len(adicionados), itens=adicionados)

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(self.create_shopping_list, name="create_shopping_list"),
            StructuredTool.from_function(
                self.add_shopping_list_product,
                name="add_shopping_list_product",
                args_schema=AddShoppingListProductArgs,
            ),
            StructuredTool.from_function(
                self.query_shopping_list,
                name="query_shopping_list",
                args_schema=QueryShoppingListArgs,
            ),
            StructuredTool.from_function(
                self.mark_purchased, name="mark_purchased", args_schema=MarkPurchasedArgs
            ),
            StructuredTool.from_function(
                self.generate_shopping_list_from_low_stock,
                name="generate_shopping_list_from_low_stock",
                args_schema=GenerateShoppingListFromLowStockArgs,
            ),
        ]


__all__ = ["ComprasRepo"]
