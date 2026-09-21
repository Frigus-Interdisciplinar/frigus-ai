"""Casos de uso de chat — `service` (abaixo) é o ponto de entrada único de todas as
interfaces (API, A2A, MCP, TUI)."""

import asyncio
from collections.abc import AsyncIterator

from frigus_ai.exceptions import ChatDeOutroUsuario, LimiteDeMensagensExcedido
from frigus_ai.graph.llm import llm_rapido
from frigus_ai.graph.prompts import load_prompt
from frigus_ai.infra.redis.rate_limit import can_send_message
from frigus_ai.logging import Logging
from frigus_ai.repositories import chat_repository
from frigus_ai.repositories.chat_repository import ChatDocument
from frigus_ai.schemas.models import ChatMessage, Role
from frigus_ai.services import runner
from frigus_ai.services.user_service import user_service
from frigus_ai.types import novo_chat_id

logger = Logging.get_logger(__name__)


def _gerar_resumo(mensagens: list[dict]) -> str:
    logger.info("Resumindo conversa...")

    conversa = "\n".join(f"{msg['role']}: {msg['content']}" for msg in mensagens)

    conteudo = llm_rapido.invoke(load_prompt("resumidor").format(conversa=conversa)).content
    assert isinstance(conteudo, str)  # texto puro, nunca multimodal, nesse prompt
    return conteudo.strip()


class ChatService:
    """Casos de uso de chat; a instância (`service`, abaixo) é o ponto de entrada."""

    async def iniciar_sessao(self, user_id: int) -> int | None:
        """Garante o perfil do usuário e resolve o stock_id. Retorna o stock_id."""

        await user_service.garantir_perfil(user_id)

        return await user_service.resolver_stock_id(user_id)

    async def criar_chat(self, user_id: int) -> str:
        await self.iniciar_sessao(user_id)
        chat_id = novo_chat_id()
        await chat_repository.criar_chat(chat_id, user_id)
        return chat_id

    async def validar_ownership(self, session_id: str, user_id: int) -> None:
        dono = await chat_repository.buscar_dono_chat(session_id)
        if dono is None:
            return
        if dono != user_id:
            raise ChatDeOutroUsuario(session_id)

    async def listar_chats(self, user_id: int) -> list[ChatDocument]:
        return await chat_repository.listar_chats(user_id)

    async def garantir_limite(self, user_id: int) -> None:
        """Consome uma unidade do rate limit; levanta se o usuário estourou a janela."""

        if not await asyncio.to_thread(can_send_message, user_id):
            raise LimiteDeMensagensExcedido(
                "Você atingiu o limite de mensagens. Tente novamente em alguns instantes."
            )

    async def send_message(
        self, conteudo: str, session_id: str, user_id: int, stock_id: int | None
    ) -> str:
        await self.garantir_limite(user_id)

        perfil = await user_service.buscar_perfil(user_id)
        resposta = await runner.executar(conteudo, session_id, user_id, stock_id, perfil)

        if not resposta:
            return "Sem resposta."

        novas = [
            ChatMessage(role=Role.HUMAN, content=conteudo),
            ChatMessage(role=Role.AI, content=resposta),
        ]
        await chat_repository.salvar_mensagens(user_id, session_id, novas)

        return resposta

    async def stream_message(
        self, conteudo: str, session_id: str, user_id: int, stock_id: int | None
    ) -> AsyncIterator[tuple[str, str]]:
        """
        Mesmo caso de uso do `send_message` (perfil, grafo, persistência), só que
        emitindo o progresso por nó enquanto o grafo roda.

        **Não** chama `garantir_limite` aqui de propósito: o corpo de um gerador só roda
        depois que a resposta HTTP começou, quando 429 já não é possível. Quem consome
        o limite no caminho SSE é a dependência da rota, antes de abrir o stream — e
        `can_send_message` incrementa contador, então chamar nos dois lugares cobraria
        duas mensagens por request.
        """

        perfil = await user_service.buscar_perfil(user_id)
        resposta = ""

        async for tipo, valor in runner.executar_stream(
            conteudo, session_id, user_id, stock_id, perfil
        ):
            if tipo == "resposta":
                resposta = valor
            yield tipo, valor

        novas = [
            ChatMessage(role=Role.HUMAN, content=conteudo),
            ChatMessage(role=Role.AI, content=resposta),
        ]
        await chat_repository.salvar_mensagens(user_id, session_id, novas)

    async def get_history(
        self, session_id: str, user_id: int, limit: int = 5
    ) -> list[ChatMessage]:
        return await chat_repository.buscar_historico(session_id, user_id, limit)

    async def encerrar_sessao(self, session_id: str, user_id: int) -> None:
        doc = await chat_repository.buscar_documento_completo(session_id, user_id)

        if doc and doc.get("messages"):
            resumo = await asyncio.to_thread(_gerar_resumo, doc["messages"])
            await chat_repository.salvar_resumo(resumo, session_id, user_id)
            await user_service.atualizar_perfil_pelo_resumo(user_id, resumo)

        await user_service.invalidar_perfil_cache(user_id)


service = ChatService()
