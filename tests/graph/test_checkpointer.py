"""Fallback do checkpointer: Mongo fora do ar só é tolerado em `local`."""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from frigus_ai.graph import builder


class _MongoFora:
    class admin:
        @staticmethod
        def command(_nome):
            raise ConnectionError("mongo fora")

    client = None


@pytest.fixture(autouse=True)
def _mongo_fora(monkeypatch):
    fake = _MongoFora()
    fake.client = fake
    monkeypatch.setattr(builder, "mongo", fake)


async def test_local_cai_pra_memory_saver(monkeypatch):
    monkeypatch.setattr(builder.settings, "environment", "local")

    assert isinstance(await builder._criar_checkpointer(), MemorySaver)


async def test_production_falha_alto(monkeypatch):
    monkeypatch.setattr(builder.settings, "environment", "production")

    with pytest.raises(ConnectionError):
        await builder._criar_checkpointer()
