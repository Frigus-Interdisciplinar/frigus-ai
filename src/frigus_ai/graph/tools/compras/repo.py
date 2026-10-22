from datetime import date

from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.compras.schemas import (
    AddShoppingListProductArgs,
    GenerateShoppingListFromLowStockArgs,
    MarkPurchasedArgs,
    QueryShoppingListArgs,
    RegisterPurchaseArgs,
)
from frigus_ai.graph.tools.estoque.helpers import compute_product_status
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.postgres.context import current_stock_id
from frigus_ai.repositories import compras_repository


class ComprasRepo(ToolSet):
    def create_shopping_list(self) -> dict:
        """
        Garante que exista uma lista de compras aberta para o estoque do usuário,
        criando uma nova se necessário. Retorna o ID da lista aberta.
        """

        list_id = compras_repository.criar_lista_aberta(current_stock_id())
        return Response.ok(shopping_list_id=list_id)

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

        final_id, final_quantity = compras_repository.adicionar_item(
            current_stock_id(), product_name, category, storage_place, quantity
        )
        return Response.ok(shopping_list_product_id=final_id, quantity=final_quantity)

    def query_shopping_list(self, status: str | None = None) -> dict:
        """
        Consulta os itens da lista de compras aberta do usuário.

        Sem filtro de status, retorna itens Pendente e Comprado (oculta Removido).
        """

        itens = compras_repository.consultar_lista(current_stock_id(), status)
        return Response.ok(total_records=len(itens), itens=itens)

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

        target_id = compras_repository.marcar_status(
            current_stock_id(), shopping_list_product_id, product_name, status
        )
        return Response.ok(shopping_list_product_id=target_id, status=status)

    def register_purchase(
        self,
        expire_date: str,
        shopping_list_product_id: int | None = None,
        product_name: str | None = None,
        quantity: int | None = None,
        unit_price: float | None = None,
    ) -> dict:
        """
        Registra a compra de um item da lista: dá entrada no estoque E marca o item como Comprado,
        numa operação só. Use quando o usuário disser que comprou algo da lista; `mark_purchased`
        sozinho só troca o status e não coloca nada no estoque.

        Localização por ID direto ou por nome do produto na lista aberta. A validade é obrigatória.
        """

        if shopping_list_product_id is None and not product_name:
            return Response.error("Informe shopping_list_product_id ou product_name.")

        validade = date.fromisoformat(expire_date)
        status = compute_product_status(validade)
        item_id, total = compras_repository.registrar_compra(
            current_stock_id(), shopping_list_product_id, product_name, validade, status, quantity, unit_price
        )
        return Response.ok(
            stock_product_id=item_id, quantity=total, expire_date=expire_date, product_status=status
        )

    def generate_shopping_list_from_low_stock(self) -> dict:
        """
        Gera/atualiza a lista de compras com base em itens do estoque abaixo da
        quantidade mínima configurada (minimal_quantity em stock_products).
        """

        adicionados = compras_repository.gerar_por_estoque_baixo(current_stock_id())
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
                self.register_purchase, name="register_purchase", args_schema=RegisterPurchaseArgs
            ),
            StructuredTool.from_function(
                self.generate_shopping_list_from_low_stock,
                name="generate_shopping_list_from_low_stock",
                args_schema=GenerateShoppingListFromLowStockArgs,
            ),
        ]


__all__ = ["ComprasRepo"]
