"""Casos de uso de usuário: bootstrap de identidade no Postgres. Persistência crua
fica em `repositories/identidade_repository.py`."""

import asyncio
from uuid import uuid4

from frigus_ai.logging import Logging
from frigus_ai.repositories import fatos_repository, identidade_repository
from frigus_ai.schemas.models import Fatos

logger = Logging.get_logger(__name__)


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

    async def buscar_fatos(self, user_id: int) -> Fatos:
        return await asyncio.to_thread(fatos_repository.buscar_fatos, user_id)

    async def sobrescrever_fatos(self, user_id: int, fatos: Fatos) -> None:
        """`PUT /profile` — correção manual do usuário, substitui tudo (inclusive
        remover alergia). Único caminho autorizado a remover alergia."""

        await asyncio.to_thread(fatos_repository.salvar_fatos, user_id, fatos)

    async def atualizar_fatos_por_extracao(self, user_id: int, fatos_extraidos: Fatos) -> None:
        """
        Merge automático (LLM, a cada N mensagens do chat) — nunca chamado pelo PUT manual.

        Alergia é informação de segurança: se o LLM "esquecer" uma alergia ao extrair
        (ex.: não apareceu nas últimas mensagens), ela não pode simplesmente sumir — daí
        a união em vez de substituição. Os demais campos não têm esse risco, então são
        substituídos pelo que a extração mais recente concluiu.
        """

        fatos_atuais = await self.buscar_fatos(user_id)
        fatos_mesclados = Fatos(
            alergias=sorted(set(fatos_atuais.alergias) | set(fatos_extraidos.alergias)),
            preferencias=fatos_extraidos.preferencias,
            restricoes=fatos_extraidos.restricoes,
            habitos=fatos_extraidos.habitos,
        )
        await asyncio.to_thread(fatos_repository.salvar_fatos, user_id, fatos_mesclados)


user_service = UserService()
