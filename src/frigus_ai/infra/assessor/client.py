"""
Cliente A2A do assessor-ai: uma operação, `SendMessage` via JSON-RPC em
`POST {ASSESSOR_A2A_URL}/a2a`, auth por `X-API-Key`.

O Assessor roda `a2a-sdk` **1.0** (conferido no OpenAPI do deploy): método `SendMessage`, header
`A2A-Version: 1.0` obrigatório, `role` como enum protobuf (`ROLE_USER`) e `parts` sem `kind`.
Envelope e resposta tipados em `schemas.py` deste pacote.

Toda falha — rede, HTTP != 2xx, corpo fora do schema, erro JSON-RPC, resposta sem texto — vira
`AssessorIndisponivel`: quem chama decide a mensagem pro usuário, o grafo nunca cai por aqui.
"""

from uuid import NAMESPACE_URL, uuid5

import httpx
from pydantic import ValidationError

from frigus_ai.exceptions import AssessorIndisponivel
from frigus_ai.infra.assessor.schemas import (
    Message,
    Part,
    Role,
    SendMessageParams,
    SendMessageRequest,
    SendMessageResponse,
)
from frigus_ai.settings import settings

_TIMEOUT = 15.0
_VERSAO_A2A = "1.0"


def context_id(session_id: str) -> str:
    """Mesmo chat do Frigus = mesmo contexto no Assessor, então ele mantém a sessão entre
    perguntas. Derivado (uuid5), não o `session_id` cru: é um ID nosso num sistema alheio."""

    return str(uuid5(NAMESPACE_URL, f"frigus/assessor/{session_id}"))


def _requisicao(pergunta: str, session_id: str) -> SendMessageRequest:
    return SendMessageRequest(
        params=SendMessageParams(
            message=Message(
                context_id=context_id(session_id),
                role=Role.USER,
                parts=[Part(text=pergunta)],
            )
        )
    )


async def perguntar(pergunta: str, session_id: str) -> str:
    if not settings.ASSESSOR_A2A_URL:
        raise AssessorIndisponivel("ASSESSOR_A2A_URL não configurada.")

    chave = settings.ASSESSOR_API_KEY.get_secret_value()
    headers = {"A2A-Version": _VERSAO_A2A, **({"X-API-Key": chave} if chave else {})}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resposta = await client.post(
                f"{settings.ASSESSOR_A2A_URL.rstrip('/')}/a2a",
                json=_requisicao(pergunta, session_id).model_dump(mode="json", exclude_none=True),
                headers=headers,
            )
            resposta.raise_for_status()
        corpo = SendMessageResponse.model_validate_json(resposta.content)
        
    except httpx.HTTPError as e:
        raise AssessorIndisponivel(f"Falha ao chamar o Assessor: {e}") from e
    except ValidationError as e:  # corpo que não é JSON ou não é uma resposta de SendMessage
        raise AssessorIndisponivel(f"Resposta inesperada do Assessor: {e}") from e

    if corpo.error:
        raise AssessorIndisponivel(f"Assessor devolveu erro JSON-RPC: {corpo.error.message}")

    texto = corpo.result.texto() if corpo.result else ""
    if not texto:
        raise AssessorIndisponivel("Assessor respondeu sem texto.")

    return texto


__all__ = ["context_id", "perguntar"]
