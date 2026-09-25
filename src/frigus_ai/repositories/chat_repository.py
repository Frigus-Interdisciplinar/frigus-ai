"""
Persistência crua da coleção `agent_chats`: histórico de mensagens e resumo de sessão
no Mongo. Sem decisão de negócio nem chamada de LLM — isso fica em
`services/chat_service.py` (que atualiza o resumo periodicamente durante a conversa,
ver `_talvez_atualizar_memoria`).
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import TypedDict

from langsmith import traceable

from frigus_ai.infra.mongo.connection import mongo
from frigus_ai.logging import Logging
from frigus_ai.privacy import anonimizar_entrada
from frigus_ai.schemas.models import ChatMessage, Role

logger = Logging.get_logger(__name__)

collection = None


class ChatDocument(TypedDict):
    """Formato do documento em `agent_chats` (leitura completa, sem projeção parcial)."""

    session_id: str
    user_id: str
    messages: list[dict]
    resume: str
    resumido_ate: int  # nº de mensagens já cobertas pelo `resume`; ausente em doc antigo = 0
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Mensagem:
    """Formato de mensagem gravado no Mongo (`agent_chats.messages`)."""

    role: Role
    content: str

    @staticmethod
    def de_dict(msgs: list[dict]) -> list["Mensagem"]:
        return [Mensagem(role=m["role"], content=m["content"]) for m in msgs]

    def para_dict(self) -> dict:
        return {"role": self.role, "content": self.content}

    @staticmethod
    def de_chat_message(msg: ChatMessage) -> "Mensagem":
        return Mensagem(role=msg.role, content=msg.content)

    def para_chat_message(self) -> ChatMessage:
        return ChatMessage(role=Role(self.role), content=self.content)


class ChatRepository:
    def __init__(self) -> None:
        self._indice_collection = None

    def _collection(self):
        return collection or mongo.collection("agent_chats")

    def _garantir_indice(self) -> None:
        colecao = self._collection()
        if colecao is not self._indice_collection:
            colecao.create_index("session_id", unique=True)
            self._indice_collection = colecao

    def _buscar_documento(self, session_id: str, user_id: str, limit: int = 5) -> ChatDocument | None:
        logger.info(f"Buscando histórico de mensagens para session_id: {session_id} (limit={limit})")

        return self._collection().find_one(
            {"session_id": session_id, "user_id": user_id},
            {"messages": {"$slice": -limit}},
        )

    def _criar_documento(self, session_id: str, user_id: str) -> None:
        agora = datetime.now(UTC)
        self._collection().update_one(
            {"session_id": session_id, "user_id": user_id},
            {"$setOnInsert": {"created_at": agora, "updated_at": agora, "messages": [], "resume": ""}},
            upsert=True,
        )

    def _buscar_dono(self, session_id: str) -> str | None:
        doc = self._collection().find_one({"session_id": session_id}, {"user_id": 1})
        return doc["user_id"] if doc else None

    def _listar_por_usuario(self, user_id: str) -> list[ChatDocument]:
        return list(self._collection().find({"user_id": user_id}).sort("updated_at", -1))

    def _adicionar_mensagens(self, session_id: str, user_id: str, mensagens: list[Mensagem]) -> None:
        logger.info(f"Adicionando mensagens para session_id: {session_id}")

        self._garantir_indice()
        agora = datetime.now(UTC)
        self._collection().update_one(
            {"session_id": session_id, "user_id": user_id},
            {
                "$push": {"messages": {"$each": [m.para_dict() for m in mensagens]}},
                "$set": {"updated_at": agora},
                "$setOnInsert": {"created_at": agora, "resume": ""},
            },
            upsert=True,
        )

    def _inserir_resumo(
        self, resumo: str, session_id: str, user_id: str, resumido_ate: int
    ) -> None:
        logger.info(f"Salvando resumo da sessão para session_id: {session_id}")

        self._collection().update_one(
            {"session_id": session_id, "user_id": user_id},
            {"$set": {"resume": resumo, "resumido_ate": resumido_ate}},
        )

    def _listar_pendentes_de_resumo(
        self, user_id: str, minimo_mensagens: int, limite: int
    ) -> list[str]:
        """session_ids dos chats com mensagens além do que o resumo cobre — os mais
        recentes primeiro. Chat abaixo do mínimo nem entra: não gasta LLM nem vaga."""

        total = {"$size": "$messages"}
        return [
            doc["session_id"]
            for doc in self._collection().aggregate([
                {"$match": {"user_id": user_id}},
                {"$match": {"$expr": {"$and": [
                    {"$gte": [total, minimo_mensagens]},
                    {"$gt": [total, {"$ifNull": ["$resumido_ate", 0]}]},
                ]}}},
                {"$sort": {"updated_at": -1}},
                {"$limit": limite},
                {"$project": {"session_id": 1}},
            ])
        ]

    def _buscar_documento_completo(self, session_id: str, user_id: str) -> ChatDocument | None:
        return self._collection().find_one({"session_id": session_id, "user_id": user_id})

    def _contar_mensagens(self, session_id: str, user_id: str) -> int:
        # `$size` via aggregate, não `find_one` + `len(doc["messages"])`: não transfere
        # o array inteiro (que só cresce) só pra saber o tamanho.
        resultado = list(self._collection().aggregate([
            {"$match": {"session_id": session_id, "user_id": user_id}},
            {"$project": {"total": {"$size": "$messages"}}},
        ]))
        return resultado[0]["total"] if resultado else 0

    async def criar_chat(self, session_id: str, user_id: str) -> None:
        await asyncio.to_thread(self._criar_documento, session_id, user_id)

    async def buscar_dono_chat(self, session_id: str) -> str | None:
        return await asyncio.to_thread(self._buscar_dono, session_id)

    async def listar_chats(self, user_id: str) -> list[ChatDocument]:
        return await asyncio.to_thread(self._listar_por_usuario, user_id)

    async def salvar_mensagens(
        self, user_id: str, session_id: str, mensagens: list[ChatMessage]
    ) -> None:
        mensagens_mongo = [Mensagem.de_chat_message(m) for m in mensagens]
        await asyncio.to_thread(self._adicionar_mensagens, session_id, user_id, mensagens_mongo)

    async def buscar_historico(
        self, session_id: str, user_id: str, limit: int = 5
    ) -> list[ChatMessage]:
        doc = await asyncio.to_thread(self._buscar_documento, session_id, user_id, limit)
        if not doc:
            return []
        return [m.para_chat_message() for m in Mensagem.de_dict(doc["messages"])]

    async def buscar_documento_completo(
        self, session_id: str, user_id: str
    ) -> ChatDocument | None:
        return await asyncio.to_thread(self._buscar_documento_completo, session_id, user_id)

    async def salvar_resumo(
        self, resumo: str, session_id: str, user_id: str, resumido_ate: int
    ) -> None:
        await asyncio.to_thread(self._inserir_resumo, resumo, session_id, user_id, resumido_ate)

    async def listar_pendentes_de_resumo(
        self, user_id: str, minimo_mensagens: int, limite: int
    ) -> list[str]:
        return await asyncio.to_thread(
            self._listar_pendentes_de_resumo, user_id, minimo_mensagens, limite
        )

    async def contar_mensagens(self, session_id: str, user_id: str) -> int:
        return await asyncio.to_thread(self._contar_mensagens, session_id, user_id)


_chat_repository = ChatRepository()


@lru_cache(maxsize=1)
def _garantir_indice() -> None:
    _chat_repository._garantir_indice()


def _buscar_documento(session_id: str, user_id: str, limit: int = 5) -> ChatDocument | None:
    return _chat_repository._buscar_documento(session_id, user_id, limit)


def _criar_documento(session_id: str, user_id: str) -> None:
    _chat_repository._criar_documento(session_id, user_id)


def _buscar_dono(session_id: str) -> str | None:
    return _chat_repository._buscar_dono(session_id)


def _listar_por_usuario(user_id: str) -> list[ChatDocument]:
    return _chat_repository._listar_por_usuario(user_id)


def _adicionar_mensagens(session_id: str, user_id: str, mensagens: list[Mensagem]) -> None:
    _chat_repository._adicionar_mensagens(session_id, user_id, mensagens)


def _inserir_resumo(resumo: str, session_id: str, user_id: str, resumido_ate: int) -> None:
    _chat_repository._inserir_resumo(resumo, session_id, user_id, resumido_ate)


def _buscar_documento_completo(session_id: str, user_id: str) -> ChatDocument | None:
    return _chat_repository._buscar_documento_completo(session_id, user_id)


# --- API pública ------------------------------------------------------------
# Só `buscar_historico`/`salvar_mensagens` levam @traceable + redação: são as únicas
# operações que carregam conteúdo de conversa (PII). As demais só manipulam IDs.

async def criar_chat(session_id: str, user_id: str) -> None:
    await _chat_repository.criar_chat(session_id, user_id)


async def buscar_dono_chat(session_id: str) -> str | None:
    return await _chat_repository.buscar_dono_chat(session_id)


async def listar_chats(user_id: str) -> list[ChatDocument]:
    return await _chat_repository.listar_chats(user_id)


def _mensagens_redigidas(mensagens: list[ChatMessage]) -> list[dict]:
    return [
        {"role": m.role.value, "content": anonimizar_entrada(m.content)[0]}
        for m in mensagens
    ]


def _redigir_entrada_mensagens(inputs: dict) -> dict:
    redigido = dict(inputs)

    if "mensagens" in redigido:
        redigido["mensagens"] = _mensagens_redigidas(redigido["mensagens"])

    return redigido


@traceable(run_type="tool", name="salvar_mensagens", process_inputs=_redigir_entrada_mensagens)
async def salvar_mensagens(user_id: str, session_id: str, mensagens: list[ChatMessage]) -> None:
    await _chat_repository.salvar_mensagens(user_id, session_id, mensagens)


def _redigir_saida_historico(historico: list[ChatMessage] | None) -> dict:
    return {"mensagens": _mensagens_redigidas(historico) if historico else []}


@traceable(run_type="tool", name="buscar_historico", process_outputs=_redigir_saida_historico)
async def buscar_historico(session_id: str, user_id: str, limit: int = 5) -> list[ChatMessage]:
    return await _chat_repository.buscar_historico(session_id, user_id, limit)


async def buscar_documento_completo(session_id: str, user_id: str) -> ChatDocument | None:
    return await _chat_repository.buscar_documento_completo(session_id, user_id)


async def salvar_resumo(resumo: str, session_id: str, user_id: str, resumido_ate: int) -> None:
    await _chat_repository.salvar_resumo(resumo, session_id, user_id, resumido_ate)


async def listar_pendentes_de_resumo(
    user_id: str, minimo_mensagens: int, limite: int
) -> list[str]:
    return await _chat_repository.listar_pendentes_de_resumo(user_id, minimo_mensagens, limite)


async def contar_mensagens(session_id: str, user_id: str) -> int:
    return await _chat_repository.contar_mensagens(session_id, user_id)
