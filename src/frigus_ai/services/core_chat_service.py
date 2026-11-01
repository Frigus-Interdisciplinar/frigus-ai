import asyncio

from frigus_ai.domain.errors import EstoqueSemAcesso
from frigus_ai.domain.recipe_turn import turno_de_receitas
from frigus_ai.repositories import identidade_repository
from frigus_ai.schemas.core_chat import CoreChatRequest, CoreChatResponse
from frigus_ai.services.chat_service import service as chat_service


class CoreChatService:
    async def conversar(self, pedido: CoreChatRequest) -> CoreChatResponse:
        user_id = str(pedido.userId)
        if not await asyncio.to_thread(identidade_repository.pode_acessar_estoque, user_id, pedido.stockId):
            raise EstoqueSemAcesso

        session_id = pedido.sessionId
        if session_id:
            await chat_service.validar_ownership(session_id, user_id)
        else:
            session_id = await chat_service.criar_chat(user_id)

        with turno_de_receitas(pedido.foodPreferences) as turno:
            resposta = await chat_service.send_message(pedido.message, session_id, user_id, pedido.stockId)

        return CoreChatResponse(sessionId=session_id, chatMessage=resposta, recipeIds=list(turno.recipes))


core_chat_service = CoreChatService()
