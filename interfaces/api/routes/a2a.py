"""
Protocolo A2A: o Agent Card no caminho de discovery (`/.well-known/agent-card.json`)
e a operação `message/send` em `POST /a2a`.

Escrito à mão em vez de usar o `a2a-sdk` (que o assessor-ai usa): o card declara
`streaming=false`/`pushNotifications=false`, então a superfície real é uma operação
só. Task store, streaming e cancelamento — o que o SDK de fato traz — seriam código
morto. Se o card passar a anunciar streaming ou tasks, o SDK passa a valer.

O `contextId` do A2A é o `session_id` do chat: é ele que faz duas chamadas caírem na
mesma conversa (mesmo `thread_id` no checkpointer). O `user_id` **não** vem do
protocolo — vem da mesma auth por `X-API-Key` das rotas de chat.
"""

from importlib.metadata import version
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from config.logging import get_logger
from config.settings import settings
from frigus_ai.chat import service as chat_service
from frigus_ai.tools.redis.schemas import CHAT_TTL_TIME
from interfaces.api.auth import CurrentUserDep
from interfaces.api.schemas.a2a import (
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    AgentSkill,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    Message,
    MessageSendParams,
    TextPart,
)

router = APIRouter(tags=["a2a"])
logger = get_logger(__name__)


SKILLS = [
    AgentSkill(
        id="estoque",
        name="Estoque de alimentos",
        description=(
            "Consulta, adiciona, atualiza quantidade e descarta itens da geladeira, "
            "freezer e despensa, incluindo o semáforo de validade."
        ),
        tags=["estoque", "validade", "alimentos"],
        examples=["O que vence essa semana?", "Tirei 2 litros de leite da geladeira"],
    ),
    AgentSkill(
        id="compras",
        name="Lista de compras",
        description=(
            "Cria e consulta a lista de compras, marca itens como comprados e gera "
            "a lista automaticamente a partir do estoque baixo."
        ),
        tags=["compras", "lista"],
        examples=["O que falta comprar?", "Marca o arroz como comprado"],
    ),
    AgentSkill(
        id="receitas",
        name="Receitas com o que tem em casa",
        description=(
            "Sugere receitas que aproveitam o estoque atual, do catálogo local e da "
            "Spoonacular, e detalha ingredientes e modo de preparo."
        ),
        tags=["receitas", "aproveitamento"],
        examples=["O que dá pra fazer com o que eu tenho?"],
    ),
    AgentSkill(
        id="financeiro",
        name="Gastos e desperdício",
        description=(
            "Responde sobre gasto mensal com alimentos, valor descartado, evolução do "
            "desperdício e comparação entre meses."
        ),
        tags=["financeiro", "desperdicio", "gastos"],
        examples=["Quanto gastei esse mês?", "Quanto joguei fora nos últimos 6 meses?"],
    ),
    AgentSkill(
        id="faq",
        name="FAQ do aplicativo Frigus",
        description="Responde dúvidas sobre o app Frigus a partir da documentação oficial (RAG).",
        tags=["faq", "rag", "suporte"],
        examples=["Como o Frigus calcula a validade dos produtos?"],
    ),
]

AGENT_CARD = AgentCard(
    protocol_version="0.3.0",
    name="Frigus.AI",
    description=(
        "Assistente conversacional multiagente de gestão de alimentos: estoque, "
        "compras, receitas, desperdício e FAQ do app Frigus."
    ),
    url=f"{settings.A2A_BASE_URL}/a2a",
    version=version("frigus-ai"),
    provider=AgentProvider(organization="Frigus", url=settings.A2A_BASE_URL),
    capabilities=AgentCapabilities(streaming=False, push_notifications=False),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=SKILLS,
)


@router.get("/.well-known/agent-card.json", response_model_by_alias=True)
async def agent_card() -> AgentCard:
    return AGENT_CARD


def _erro(id_req, codigo: int, mensagem: str) -> JsonRpcResponse:
    return JsonRpcResponse(id=id_req, error=JsonRpcError(code=codigo, message=mensagem))


# exclude_none: o JSON-RPC 2.0 proíbe `result` e `error` no mesmo objeto — sem isso
# a resposta de erro sairia com `"result": null` junto.
@router.post("/a2a", response_model_exclude_none=True)
async def message_send(payload: JsonRpcRequest, user_id: CurrentUserDep) -> JsonRpcResponse:
    """
    Erro de protocolo volta como objeto `error` do JSON-RPC (HTTP 200, como manda o
    JSON-RPC 2.0). Falha de transporte — auth, rate limit, erro interno — volta como
    status HTTP, onde um cliente A2A espera encontrá-la.

    Exceção conhecida: body que nem chega a ser um envelope JSON-RPC válido é barrado
    pelo Pydantic e sai como **422**, não como `-32600`. Deixado assim de propósito —
    validar o envelope à mão só pra trocar o código de erro não paga.
    """

    if payload.method != "message/send":
        return _erro(payload.id, -32601, f"Método não suportado: {payload.method}")

    try:
        params = MessageSendParams.model_validate(payload.params)
    except ValueError:
        return _erro(payload.id, -32602, "params inválidos para message/send.")

    # Sem contextId o cliente está abrindo conversa nova — devolvemos o id gerado
    # para ele reusar na próxima chamada.
    session_id = params.message.context_id or str(uuid4())
    stock_id = await chat_service.iniciar_sessao(user_id)
    try:
        resposta = await chat_service.send_message(
            params.message.texto(), session_id, user_id, stock_id
        )

    except chat_service.LimiteDeMensagensExcedido as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            str(e),
            headers={"Retry-After": str(CHAT_TTL_TIME)},
        ) from e

    except Exception as e:
        logger.exception("Falha em message/send | context_id=%s", session_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Erro interno ao processar a mensagem."
        ) from e

    return JsonRpcResponse(
        id=payload.id,
        result=Message(
            message_id=str(uuid4()),
            context_id=session_id,
            role="agent",
            parts=[TextPart(text=resposta)],
        ),
    )
