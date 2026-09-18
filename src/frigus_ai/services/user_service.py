"""Casos de uso de usuário: bootstrap de identidade no Postgres e cache-aside do
perfil comportamental (Redis na frente do Mongo). Persistência crua fica em
`repositories/user_repository.py`."""

import asyncio
from uuid import uuid4

from langsmith import traceable

from frigus_ai.graph.llm import llm_rapido
from frigus_ai.graph.prompts import load_prompt
from frigus_ai.logging import Logging
from frigus_ai.privacy import anonimizar_entrada
from frigus_ai.repositories import identidade_repository, user_repository

logger = Logging.get_logger(__name__)


def _redigir_saida_perfil(perfil: str | None) -> dict:
    texto, _ = anonimizar_entrada(perfil or "")
    return {"perfil": texto}


def _gerar_perfil(perfil_atual: str, resumo: str) -> str:
    logger.info("Atualizando perfil do usuário...")

    conteudo = llm_rapido.invoke(
        load_prompt("perfil").format(perfil_atual=perfil_atual, resumo=resumo)
    ).content
    assert isinstance(conteudo, str)  # texto puro, nunca multimodal, nesse prompt
    return conteudo.strip()


class UserService:
    """Casos de uso de usuário; a instância (`user_service`, abaixo) é o ponto de entrada."""

    async def criar_usuario(self, nome: str, email: str) -> int:
        return await asyncio.to_thread(identidade_repository.criar_usuario, nome, email)

    async def resolver_stock_id(self, user_id: int) -> int | None:
        return await asyncio.to_thread(identidade_repository.resolver_stock_id, user_id)

    async def obter_ou_criar_padrao(self) -> int:
        """
        Reaproveita o primeiro usuário existente no Postgres, ou cria um novo. Bootstrap
        usado pela TUI e pela API quando `API_KEY_AUTH_ENABLED=false` (sem tela de
        login) — substitui o antigo `DEMO_USER_ID` fixo, que assumia que o id 1 sempre
        existia no banco.
        """

        existente = await asyncio.to_thread(identidade_repository.buscar_primeiro_usuario)
        if existente is not None:
            return existente

        return await self.criar_usuario("Usuário Local", f"local-{uuid4()}@frigus.local")

    async def garantir_perfil(self, user_id: int) -> None:
        await asyncio.to_thread(user_repository.garantir_perfil, user_id)

    @traceable(run_type="tool", name="buscar_perfil", process_outputs=_redigir_saida_perfil)
    async def buscar_perfil(self, user_id: int) -> str:
        """Cache-aside: tenta o Redis primeiro, só bate no Mongo em caso de miss."""

        perfil_cache = await asyncio.to_thread(user_repository.buscar_perfil_cache, user_id)
        if perfil_cache is not None:
            return perfil_cache

        perfil = await asyncio.to_thread(user_repository.buscar_perfil, user_id)
        await asyncio.to_thread(user_repository.salvar_perfil_cache, user_id, perfil)
        return perfil

    async def invalidar_perfil_cache(self, user_id: int) -> None:
        await asyncio.to_thread(user_repository.invalidar_perfil_cache, user_id)

    async def atualizar_perfil_pelo_resumo(self, user_id: int, resumo: str) -> None:
        """
        Regenera o perfil comportamental a partir do resumo da sessão que acabou de
        encerrar. Lê o perfil atual direto do Mongo, sem cache: o valor está prestes
        a ser sobrescrito, então passar pelo Redis aqui só arriscaria ler algo stale
        e popular o cache com um perfil que já nasce desatualizado.
        """

        perfil_atual = await asyncio.to_thread(user_repository.buscar_perfil, user_id)
        perfil_atualizado = await asyncio.to_thread(_gerar_perfil, perfil_atual, resumo)
        await asyncio.to_thread(user_repository.atualizar_perfil, user_id, perfil_atualizado)


user_service = UserService()
