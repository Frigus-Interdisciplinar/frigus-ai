import asyncio

from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.preferencias.schemas import (
    DefinirPreferenciaArgs,
    ListarPreferenciasArgs,
    RemoverPreferenciaArgs,
    SugerirReceitasCompativeisArgs,
)
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.postgres.context import current_user_id
from frigus_ai.repositories import preferencias_repository
from frigus_ai.repositories.preferencias_repository import TipoPreferencia


def _uid_do_grafo() -> str:
    """Converte o user_id da sessão (Postgres, int) pro uid do node User no Neo4j."""
    return f"user-{current_user_id()}"


class PreferenciasRepo(ToolSet):
    async def listar_preferencias(self) -> dict:
        """
        Retorna os ingredientes que o usuário prefere, não gosta ou é alérgico,
        de acordo com o grafo de preferências.
        """

        preferencias = await preferencias_repository.listar_preferencias(_uid_do_grafo())
        return Response.ok(**preferencias)

    async def definir_preferencia(self, ingrediente_nome: str, tipo: TipoPreferencia) -> dict:
        """
        Marca um ingrediente como preferido, não gostado ou alérgico para o usuário.
        """

        await preferencias_repository.definir_preferencia(_uid_do_grafo(), ingrediente_nome, tipo)
        return Response.ok(ingrediente_nome=ingrediente_nome, tipo=tipo)

    async def remover_preferencia(self, ingrediente_nome: str, tipo: TipoPreferencia) -> dict:
        """
        Remove a marcação de um ingrediente como preferido, não gostado ou alérgico.
        """

        await preferencias_repository.remover_preferencia(_uid_do_grafo(), ingrediente_nome, tipo)
        return Response.ok(ingrediente_nome=ingrediente_nome, tipo=tipo)

    async def sugerir_receitas_compativeis(self, limit: int = 10) -> dict:
        """
        Sugere receitas que não usam nenhum ingrediente que o usuário não gosta ou é
        alérgico, cruzando o grafo de preferências com o grafo de receitas.
        """

        receitas = await preferencias_repository.receitas_sem_restricoes(_uid_do_grafo(), limit)
        return Response.ok(total_records=len(receitas), receitas=receitas)

    def as_tools(self) -> list[BaseTool]:
        def listar_sync(**kwargs):
            """Executa a consulta de preferências para callers síncronos legados."""
            return asyncio.run(self.listar_preferencias(**kwargs))

        def definir_sync(**kwargs):
            """Executa a marcação de preferência para callers síncronos legados."""
            return asyncio.run(self.definir_preferencia(**kwargs))

        def remover_sync(**kwargs):
            """Executa a remoção de preferência para callers síncronos legados."""
            return asyncio.run(self.remover_preferencia(**kwargs))

        def sugerir_sync(**kwargs):
            """Executa a sugestão de receitas compatíveis para callers síncronos legados."""
            return asyncio.run(self.sugerir_receitas_compativeis(**kwargs))

        return [
            StructuredTool.from_function(
                listar_sync,
                coroutine=self.listar_preferencias,
                name="listar_preferencias",
                description=self.listar_preferencias.__doc__,
                args_schema=ListarPreferenciasArgs,
            ),
            StructuredTool.from_function(
                definir_sync,
                coroutine=self.definir_preferencia,
                name="definir_preferencia",
                description=self.definir_preferencia.__doc__,
                args_schema=DefinirPreferenciaArgs,
            ),
            StructuredTool.from_function(
                remover_sync,
                coroutine=self.remover_preferencia,
                name="remover_preferencia",
                description=self.remover_preferencia.__doc__,
                args_schema=RemoverPreferenciaArgs,
            ),
            StructuredTool.from_function(
                sugerir_sync,
                coroutine=self.sugerir_receitas_compativeis,
                name="sugerir_receitas_compativeis",
                description=self.sugerir_receitas_compativeis.__doc__,
                args_schema=SugerirReceitasCompativeisArgs,
            ),
        ]


__all__ = ["PreferenciasRepo"]
