"""Casos de uso de receitas: leitura (sugestão é gerada, não editada) e favoritos do usuário."""

import asyncio
import re
from typing import Literal

from frigus_ai.domain.errors import ReceitaNaoEncontrada
from frigus_ai.graph.tools.preferencias.repo import _sem_anotacao
from frigus_ai.graph.tools.spoonacular.repo import detalhar_receita
from frigus_ai.infra.logging import Logging
from frigus_ai.repositories import (
    favoritos_repository,
    grafo_receitas_repository,
    receitas_repository,
)
from frigus_ai.schemas.recipes import (
    NutrientResponse,
    RecipeDetailResponse,
    RecipeIngredientResponse,
    RecipeSuggestionResponse,
    RecipeSummaryResponse,
)
from frigus_ai.services.user_service import user_service

logger = Logging.get_logger(__name__)

# Janela em que um ingrediente passa a ter prioridade na sugestão.
DIAS_VENCIMENTO_PRIORITARIO = 7

type Source = Literal["local", "spoonacular"]

_TAG_HTML = re.compile(r"<[^>]+>")


def _etapas(texto: str | None) -> list[str]:
    if not texto:
        return []

    sem_html = _TAG_HTML.sub("\n", texto)

    return [linha.strip() for linha in sem_html.splitlines() if linha.strip()]


class RecipeService:
    async def listar(self, user_id: str, limit: int, query: str | None = None) -> list[RecipeSummaryResponse]:
        receitas = await asyncio.to_thread(receitas_repository.listar_receitas, limit, query)
        favoritas = await self._chaves_favoritas(user_id)

        return [
            RecipeSummaryResponse(**receita, is_favorite=("local", receita["recipe_id"]) in favoritas)
            for receita in receitas
        ]

    async def favoritar(self, user_id: str, source: Source, recipe_id: int) -> None:
        # Detalhar antes valida que a receita existe e tira o retrato do card.
        receita = await self._detalhe(source, recipe_id, include_nutrition=False)

        await asyncio.to_thread(
            favoritos_repository.favoritar,
            user_id,
            {"source": source, "recipe_id": recipe_id, "name": receita.name, "image_url": receita.image_url},
        )

    async def desfavoritar(self, user_id: str, source: Source, recipe_id: int) -> None:
        await asyncio.to_thread(favoritos_repository.desfavoritar, user_id, source, recipe_id)

    async def favoritas(self, user_id: str, limit: int) -> list[RecipeSummaryResponse]:
        favoritos = await asyncio.to_thread(favoritos_repository.listar_favoritos, user_id, limit)

        return [
            RecipeSummaryResponse(
                recipe_id=f["recipe_id"],
                source=f["source"],
                name=f["name"],
                image_url=f["image_url"],
                is_favorite=True,
            )
            for f in favoritos
        ]

    async def _chaves_favoritas(self, user_id: str) -> set[tuple[str, int]]:
        # ponytail: teto de 500 favoritos pra marcar o card; paginar se alguém passar disso.
        favoritos = await asyncio.to_thread(favoritos_repository.listar_favoritos, user_id, 500)

        return {(f["source"], f["recipe_id"]) for f in favoritos}

    async def sincronizar_grafo(self) -> int:
        """Projeta as receitas ativas do Postgres no Neo4j. Devolve quantas foram enviadas (novas ou alteradas)."""

        receitas = await asyncio.to_thread(receitas_repository.listar_com_ingredientes)

        return await grafo_receitas_repository.sincronizar(receitas)

    async def sugerir(self, user_id: str, stock_id: int, limit: int) -> list[RecipeSuggestionResponse]:
        """
        Sugestão pelo grafo (estoque + vencimento + alergias + preferências). Neo4j fora do ar
        degrada pro cruzamento em SQL em vez de derrubar a tela.
        """

        try:
            return await self._sugerir_pelo_grafo(user_id, stock_id, limit)
        except Exception:
            logger.exception("Neo4j indisponível; sugestão pelo cruzamento em SQL")
            sugestoes = await asyncio.to_thread(receitas_repository.match_recipes_to_stock, stock_id, limit)

            return [RecipeSuggestionResponse(**sugestao) for sugestao in sugestoes]

    async def _sugerir_pelo_grafo(self, user_id: str, stock_id: int, limit: int) -> list[RecipeSuggestionResponse]:
        fatos = await user_service.buscar_fatos(user_id)
        preferencias = await user_service.buscar_preferencias_receitas(user_id)
        estoque = await asyncio.to_thread(
            receitas_repository.estoque_utilizavel, stock_id, DIAS_VENCIMENTO_PRIORITARIO
        )
        validade_por_chave = {item["key"]: item["expire_date"] for item in estoque}

        sugestoes = await grafo_receitas_repository.sugerir(
            disponiveis=list(validade_por_chave),
            prioritarios=[item["key"] for item in estoque if item["prioritario"]],
            evitar=[_sem_anotacao(alergia) for alergia in fatos.alergias],
            preferir_economicas=preferencias.preferir_economicas,
            limite=limit,
        )

        return [
            self._sugestao_do_grafo(s, validade_por_chave, preferencias.restricoes) for s in sugestoes
        ]

    @staticmethod
    def _sugestao_do_grafo(sugestao, validade_por_chave, restricoes: list[str]) -> RecipeSuggestionResponse:
        encontrados = sugestao["encontrados"]
        faltantes = sugestao["faltantes"]
        vencendo = sugestao["prioritarios"]
        validades = [validade_por_chave[i["key"]] for i in encontrados if i["key"] in validade_por_chave]

        if vencendo:
            motivo = f"Usa {', '.join(vencendo)}, que vence em até {DIAS_VENCIMENTO_PRIORITARIO} dias."
        elif not faltantes:
            motivo = "Você tem todos os ingredientes."
        else:
            motivo = f"Você tem {len(encontrados)} de {len(encontrados) + len(faltantes)} ingredientes."

        return RecipeSuggestionResponse(
            recipe_id=sugestao["recipe_id"],
            name=sugestao["name"],
            matched_ingredients=len(encontrados),
            missing_ingredients=len(faltantes),
            nearest_expire_date=str(min(validades)) if validades else None,
            score=round(sugestao["score"], 3),
            expiring_ingredients=vencendo,
            matched_ingredient_names=[i["name"] for i in encontrados],
            missing_ingredient_names=faltantes,
            reason=motivo,
            # Nenhuma receita tem restrição alimentar verificada: sinaliza em vez de prometer segurança.
            unverified_restrictions=restricoes,
        )

    async def detalhar(
        self, user_id: str, source: Source, recipe_id: int, include_nutrition: bool
    ) -> RecipeDetailResponse:
        receita = await self._detalhe(source, recipe_id, include_nutrition)
        receita.is_favorite = (source, recipe_id) in await self._chaves_favoritas(user_id)

        return receita

    async def _detalhe(self, source: Source, recipe_id: int, include_nutrition: bool) -> RecipeDetailResponse:
        if source == "spoonacular":
            return await self._detalhar_spoonacular(recipe_id, include_nutrition)

        receita = await asyncio.to_thread(receitas_repository.get_recipe_details, recipe_id)
        if receita is None:
            raise ReceitaNaoEncontrada

        return RecipeDetailResponse(
            recipe_id=receita["recipe_id"],
            name=receita["name"],
            description=receita["description"],
            ingredients=[
                RecipeIngredientResponse(
                    name=i["product_name"], quantity=i["quantity"], unit=i["unit"]
                )
                for i in receita["ingredientes"]
            ],
            steps=_etapas(receita["instructions"]),
        )

    async def _detalhar_spoonacular(self, recipe_id: int, include_nutrition: bool) -> RecipeDetailResponse:
        receita = await detalhar_receita(recipe_id, include_nutrition)

        etapas = [e.step for grupo in receita.preparo for e in grupo.steps]

        return RecipeDetailResponse(
            recipe_id=receita.id,
            source="spoonacular",
            name=receita.title,
            image_url=receita.image_url,
            ready_in_minutes=receita.ready_in_minutes,
            servings=receita.servings,
            ingredients=[
                RecipeIngredientResponse(name=i.nome, quantity=i.quantidade, unit=i.unidade)
                for i in receita.ingredientes
            ],
            steps=etapas or _etapas(receita.instrucoes),
            source_name=receita.source_name,
            source_url=receita.source_url,
            credits_text=receita.credits_text,
            nutrients=(
                [NutrientResponse(**n.model_dump()) for n in receita.nutrition.nutrients]
                if receita.nutrition
                else None
            ),
        )


recipe_service = RecipeService()
