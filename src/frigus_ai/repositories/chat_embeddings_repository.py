"""
Resumos de chat no Qdrant (um ponto por chat) pra recuperar conversas anteriores relevantes.
O ID é `uuid5` do `session_id`, então cada resumo novo sobrescreve o anterior, mesmo após
reiniciar (`hash()` do Python varia por processo).
"""

from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient, models

from frigus_ai.domain.privacy import redigir_pii
from frigus_ai.infra.qdrant import get_async_qdrant_client, get_embeddings
from frigus_ai.settings import settings
from frigus_ai.telemetry.metrics import MEMORY_RETRIEVAL_HITS, medir_externo

_LIMITE = 3
_SCORE_MINIMO = 0.7


def _id_do_ponto(session_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frigus/chat/{session_id}"))


class ChatEmbeddingsRepository:
    def __init__(self) -> None:
        self._indices_ok = False

    def _client(self) -> AsyncQdrantClient:
        return get_async_qdrant_client()

    def _nome(self) -> str:
        return settings.database.qdrant_chats_collection

    async def _existe(self) -> bool:
        return await self._client().collection_exists(self._nome())

    async def _garantir_indices(self) -> None:
        """
        Qdrant Cloud recusa filtro em campo sem índice (400), então indexa `user_id` e `session_id`.
        Idempotente: roda uma vez por processo, também pra collection criada antes do índice novo.
        """

        if self._indices_ok:
            return

        for campo in ("user_id", "session_id"):
            await self._client().create_payload_index(
                self._nome(), campo, models.PayloadSchemaType.KEYWORD
            )
        self._indices_ok = True

    async def _garantir_collection(self, tamanho_vetor: int) -> None:
        if not await self._existe():
            await self._client().create_collection(
                collection_name=self._nome(),
                vectors_config=models.VectorParams(size=tamanho_vetor, distance=models.Distance.COSINE),
            )
        await self._garantir_indices()

    async def salvar_resumo(self, session_id: str, user_id: str, resumo: str) -> None:
        # PII fica no Mongo (histórico do próprio usuário), mas não é copiada pro índice vetorial.
        resumo = redigir_pii(resumo)
        with medir_externo("gemini_embed"):
            [vetor] = await get_embeddings("retrieval_document").aembed_documents([resumo])

        with medir_externo("qdrant"):
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
        self, user_id: str, pergunta: str, session_id_atual: str
    ) -> list[str]:
        if not await self._existe():
            return []

        await self._garantir_indices()

        with medir_externo("gemini_embed"):
            vetor = await get_embeddings("retrieval_query").aembed_query(redigir_pii(pergunta))

        with medir_externo("qdrant"):
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

        resumos = [p.payload["resumo"] for p in resultado.points if p.payload]
        MEMORY_RETRIEVAL_HITS.observe(len(resumos))
        return resumos


_chat_embeddings_repository = ChatEmbeddingsRepository()


async def salvar_resumo(session_id: str, user_id: str, resumo: str) -> None:
    await _chat_embeddings_repository.salvar_resumo(session_id, user_id, resumo)


async def remover_resumo(session_id: str) -> None:
    await _chat_embeddings_repository.remover_resumo(session_id)


async def buscar_resumos_relevantes(
    user_id: str, pergunta: str, session_id_atual: str
) -> list[str]:
    return await _chat_embeddings_repository.buscar_resumos_relevantes(
        user_id, pergunta, session_id_atual
    )


__all__ = ["buscar_resumos_relevantes", "remover_resumo", "salvar_resumo"]
