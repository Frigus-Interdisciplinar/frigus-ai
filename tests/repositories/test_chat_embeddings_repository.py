"""
Resumos de chat no Qdrant, com o client em memória (`:memory:`) e embedding falso — sem
rede. O que se protege: um ponto por chat (upsert pelo ID determinístico, não duplica),
busca isolada por dono e sem trazer o próprio chat atual.
"""

import pytest
from qdrant_client import AsyncQdrantClient

from frigus_ai.repositories import chat_embeddings_repository as repo
from frigus_ai.settings import settings


class _FakeEmbeddings:
    """Vetor pelo assunto: 'leite' e 'arroz' ficam ortogonais, então o score separa."""

    @staticmethod
    def _vetor(texto):
        return [1.0, 0.0] if "leite" in texto else [0.0, 1.0]

    async def aembed_documents(self, textos):
        return [self._vetor(t) for t in textos]

    async def aembed_query(self, texto):
        return self._vetor(texto)


@pytest.fixture
def client(monkeypatch):
    client = AsyncQdrantClient(":memory:")
    monkeypatch.setattr(repo, "get_async_qdrant_client", lambda: client)
    monkeypatch.setattr(repo, "get_embeddings", lambda _task: _FakeEmbeddings())
    return client


async def _total(client):
    return (await client.count(settings.QDRANT_CHATS_COLLECTION)).count


def test_id_do_ponto_e_deterministico_por_chat():
    """uuid5, não hash(): o mesmo chat cai no mesmo ponto mesmo depois de reiniciar."""

    assert repo._id_do_ponto("chat-1") == repo._id_do_ponto("chat-1")
    assert repo._id_do_ponto("chat-1") != repo._id_do_ponto("chat-2")


async def test_novo_resumo_do_mesmo_chat_sobrescreve(client):
    await repo.salvar_resumo("chat-1", 7, "comprou leite")
    await repo.salvar_resumo("chat-1", 7, "comprou leite e decidiu trocar de marca")

    assert await _total(client) == 1


async def test_busca_so_traz_chats_do_dono_e_nao_o_atual(client):
    await repo.salvar_resumo("chat-1", 7, "comprou leite")
    await repo.salvar_resumo("chat-2", 7, "falou de leite de novo")
    await repo.salvar_resumo("chat-3", 99, "outro usuário, leite")

    resumos = await repo.buscar_resumos_relevantes(7, "e o leite?", session_id_atual="chat-2")

    assert resumos == ["comprou leite"]


async def test_busca_ignora_resumo_de_outro_assunto(client):
    await repo.salvar_resumo("chat-1", 7, "planejou arroz da semana")

    assert await repo.buscar_resumos_relevantes(7, "e o leite?", "chat-atual") == []


async def test_remover_tira_o_ponto(client):
    await repo.salvar_resumo("chat-1", 7, "comprou leite")
    await repo.remover_resumo("chat-1")

    assert await _total(client) == 0


async def test_sem_collection_busca_e_remocao_nao_falham(client):
    assert await repo.buscar_resumos_relevantes(7, "leite", "chat-1") == []
    await repo.remover_resumo("chat-1")


async def test_pii_nao_vai_pro_indice(client):
    await repo.salvar_resumo("chat-1", 7, "leite; CPF 123.456.789-01")

    [ponto] = (await client.scroll(settings.QDRANT_CHATS_COLLECTION))[0]
    assert "123.456.789-01" not in ponto.payload["resumo"]
