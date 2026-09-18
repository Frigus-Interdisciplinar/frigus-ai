"""
Integração A2A do Frigus via `a2a-sdk`.

Hoje não é montada em `api/app.py` — a rota A2A ativa é a manual em
`api/routes/a2a.py` (ver docstring de lá pra saber por quê). Este módulo fica como
integração alternativa via SDK, pra quando o card precisar anunciar streaming/tasks.
"""

import asyncio
from importlib.metadata import version
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    InvalidParamsError,
    Message,
    Part,
    Role,
    TaskNotCancelableError,
)
from fastapi import FastAPI

from frigus_ai.infra.redis import session as session_cache
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service
from frigus_ai.settings import settings

SKILLS = [
    AgentSkill(
        id="estoque",
        name="Estoque de alimentos",
        description="Consulta e atualiza os alimentos armazenados e suas validades.",
        tags=["estoque", "validade", "alimentos"],
        examples=["O que vence essa semana?"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    ),
    AgentSkill(
        id="compras",
        name="Lista de compras",
        description="Consulta e atualiza a lista de compras do usuário.",
        tags=["compras", "lista"],
        examples=["O que falta comprar?"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    ),
    AgentSkill(
        id="receitas",
        name="Receitas",
        description="Sugere receitas com os alimentos disponíveis.",
        tags=["receitas", "aproveitamento"],
        examples=["O que dá para fazer com o que eu tenho?"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    ),
    AgentSkill(
        id="financeiro",
        name="Finanças domésticas",
        description="Consulta gastos e desperdício de alimentos.",
        tags=["financeiro", "gastos", "desperdício"],
        examples=["Quanto gastei este mês?"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    ),
    AgentSkill(
        id="faq",
        name="FAQ do Frigus",
        description="Responde dúvidas sobre o aplicativo a partir da documentação oficial.",
        tags=["faq", "rag"],
        examples=["Como o Frigus calcula a validade?"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    ),
]

AGENT_CARD = AgentCard(
    name="Frigus.AI",
    description="Assistente conversacional multiagente para gestão de alimentos.",
    version=version("frigus-ai"),
    provider=AgentProvider(organization="Frigus", url=settings.A2A_BASE_URL),
    supported_interfaces=[
        AgentInterface(
            url=f"{settings.A2A_BASE_URL}/a2a",
            protocol_binding="JSONRPC",
            protocol_version="1.0",
        )
    ],
    capabilities=AgentCapabilities(streaming=False, push_notifications=False),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=SKILLS,
)


async def _sessao_para(context_id: str) -> tuple[int, str]:
    user_id = await asyncio.to_thread(session_cache.buscar_usuario_da_sessao, context_id)
    if user_id is not None:
        return user_id, context_id

    user_id = await user_service.obter_ou_criar_padrao()
    gravou = await asyncio.to_thread(
        session_cache.salvar_usuario_da_sessao, context_id, user_id
    )
    if not gravou:
        user_id = await asyncio.to_thread(
            session_cache.buscar_usuario_da_sessao, context_id
        )
        if user_id is None:
            raise RuntimeError("Não foi possível criar a sessão A2A.")

    return user_id, context_id


class FrigusAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.context_id is None:
            raise InvalidParamsError(message="context_id é obrigatório.")

        user_id, session_id = await _sessao_para(context.context_id)
        stock_id = await chat_service.iniciar_sessao(user_id)
        resposta = await chat_service.send_message(
            context.get_user_input(), session_id, user_id, stock_id
        )
        await event_queue.enqueue_event(
            Message(
                message_id=str(uuid4()),
                context_id=context.context_id,
                role=Role.ROLE_AGENT,
                parts=[Part(text=resposta)],
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise TaskNotCancelableError()


def montar_rotas(app: FastAPI) -> None:
    handler = DefaultRequestHandler(
        agent_executor=FrigusAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=AGENT_CARD,
    )
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(AGENT_CARD),
        jsonrpc_routes=create_jsonrpc_routes(
            handler, rpc_url="/a2a", enable_v0_3_compat=True
        ),
    )
