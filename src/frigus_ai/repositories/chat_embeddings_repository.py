"""
Resumos de chat no Qdrant: um ponto por chat, pra recuperar conversas anteriores
relevantes à pergunta atual. Quem decide O QUE entra é `services/chat_service.py`
(só resumo marcado `relevante`); aqui é só persistência + busca.

O ID do ponto é `uuid5` do `session_id`: o mesmo chat sempre cai no mesmo ponto, então
cada resumo novo sobrescreve o anterior (upsert) em vez de duplicar — inclusive depois
de reiniciar o processo, o que `hash()` do Python não garante (PYTHONHASHSEED).
"""

from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient, models

from frigus_ai.infra.qdrant.connection import get_async_qdrant_client, get_embeddings
from frigus_ai.privacy import redigir_pii
from frigus_ai.settings import settings

_LIMITE = 3
_SCORE_MINIMO = 0.7


def _id_do_ponto(session_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frigus/chat/{session_id}"))


class ChatEmbeddingsRepository:
    def _client(self) -> AsyncQdrantClient:
        return get_async_qdrant_client()

    def _nome(self) -> str:
        return settings.QDRANT_CHATS_COLLECTION

    async def _existe(self) -> bool:
        return await self._client().collection_exists(self._nome())

    async def _garantir_collection(self, tamanho_vetor: int) -> None:
        if await self._existe():
            return

        await self._client().create_collection(
            collection_name=self._nome(),
            vectors_config=models.VectorParams(size=tamanho_vetor, distance=models.Distance.COSINE),
        )
        # Toda busca filtra por dono — sem índice, o filtro varre o payload de todo ponto.
        await self._client().create_payload_index(
            self._nome(), "user_id", models.PayloadSchemaType.INTEGER
        )

    async def salvar_resumo(self, session_id: str, user_id: int, resumo: str) -> None:
        # PII fica no Mongo (histórico do próprio usuário), mas não é copiada pro índice vetorial.
        resumo = redigir_pii(resumo)
        [vetor] = await get_embeddings("retrieval_document").aembed_documents([resumo])
        await self._garantir_collection(len(vetor))

        await self._client().upsert(
            collection_name=self._nome(),
            points=[
                models.PointStruct(
                    id=_id_do_ponto(session_id),
                    vector=vetor,
                    payload={"user_id": user_id, "session_id": session_id, "resumo": resumo},
                )
            ],
        )

    async def remover_resumo(self, session_id: str) -> None:
        if not await self._existe():
            return

        await self._client().delete(
            collection_name=self._nome(),
            points_selector=models.PointIdsList(points=[_id_do_ponto(session_id)]),
        )

    async def buscar_resumos_relevantes(
        self, user_id: int, pergunta: str, session_id_atual: str
    ) -> list[str]:
        if not await self._existe():
            return []

        vetor = await get_embeddings("retrieval_query").aembed_query(redigir_pii(pergunta))
        resultado = await self._client().query_points(
            collection_name=self._nome(),
            query=vetor,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id)
                    )
                ],
                must_not=[
                    models.FieldCondition(
                        key="session_id",
                        match=models.MatchValue(value=session_id_atual)
                    )
                ],
            ),
            limit=_LIMITE,
            score_threshold=_SCORE_MINIMO,
        )

        return [p.payload["resumo"] for p in resultado.points if p.payload]


_chat_embeddings_repository = ChatEmbeddingsRepository()


async def salvar_resumo(session_id: str, user_id: int, resumo: str) -> None:
    await _chat_embeddings_repository.salvar_resumo(session_id, user_id, resumo)


async def remover_resumo(session_id: str) -> None:
    await _chat_embeddings_repository.remover_resumo(session_id)


async def buscar_resumos_relevantes(
    user_id: int, pergunta: str, session_id_atual: str
) -> list[str]:
    return await _chat_embeddings_repository.buscar_resumos_relevantes(
        user_id, pergunta, session_id_atual
    )


__all__ = ["buscar_resumos_relevantes", "remover_resumo", "salvar_resumo"]
