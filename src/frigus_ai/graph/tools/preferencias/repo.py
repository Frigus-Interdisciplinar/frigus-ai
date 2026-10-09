import asyncio
import re

from langchain_core.tools import BaseTool, StructuredTool

from frigus_ai.graph.tools.base import ToolSet
from frigus_ai.graph.tools.preferencias.schemas import SugerirReceitasCompativeisArgs
from frigus_ai.graph.tools.response import Response
from frigus_ai.infra.postgres.context import current_user_id
from frigus_ai.repositories import preferencias_repository
from frigus_ai.services.user_service import user_service


def _sem_anotacao(alergia: str) -> str:
    """"Amendoim (filho)" → "Amendoim": o grafo só conhece o nome do ingrediente."""
    return re.sub(r"\s*\(.*?\)", "", alergia)


class PreferenciasRepo(ToolSet):
    async def sugerir_receitas_compativeis(self, evitar: list[str] | None = None, limit: int = 10) -> dict:
        """
        Sugere receitas do grafo de receitas que não usam nenhum ingrediente ao qual o
        usuário (ou alguém da casa) é alérgico — as alergias do perfil já são aplicadas
        automaticamente. Use `evitar` para excluir também ingredientes que ele não gosta.
        """

        fatos = await user_service.buscar_fatos(current_user_id())
        evitar_total = [*map(_sem_anotacao, fatos.alergias), *(evitar or [])]

        receitas = await preferencias_repository.receitas_sem_ingredientes(evitar_total, limit)
        return Response.ok(total_records=len(receitas), receitas=receitas)

    def as_tools(self) -> list[BaseTool]:
        def sugerir_sync(**kwargs):
            """Executa a sugestão de receitas compatíveis para callers síncronos legados."""
            return asyncio.run(self.sugerir_receitas_compativeis(**kwargs))

        return [
            StructuredTool.from_function(
                sugerir_sync,
                coroutine=self.sugerir_receitas_compativeis,
                name="sugerir_receitas_compativeis",
                description=self.sugerir_receitas_compativeis.__doc__,
                args_schema=SugerirReceitasCompativeisArgs,
            ),
        ]


__all__ = ["PreferenciasRepo"]
