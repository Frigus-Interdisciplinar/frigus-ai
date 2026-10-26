"""Favorito é idempotente e isolado por usuário: a chave do upsert inclui user_id + source + recipe_id."""

import frigus_ai.repositories.favoritos_repository as repo


class _FakeCollection:
    def __init__(self):
        self.updates = []
        self.deletes = []
        self.indices = []

    def create_index(self, chaves, unique=False):
        self.indices.append((chaves, unique))

    def update_one(self, filtro, update, upsert=False):
        self.updates.append((filtro, upsert))

    def delete_one(self, filtro):
        self.deletes.append(filtro)


def test_favoritar_e_upsert_pela_chave_unica(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(repo, "collection", fake)
    repo._favoritos._indice_collection = None

    repo.favoritar("u1", {"source": "local", "recipe_id": 4, "name": "x", "image_url": None})

    assert fake.updates == [({"user_id": "u1", "source": "local", "recipe_id": 4}, True)]
    assert fake.indices[0][1] is True


def test_desfavoritar_filtra_por_usuario(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(repo, "collection", fake)

    repo.desfavoritar("u1", "spoonacular", 7)

    assert fake.deletes == [{"user_id": "u1", "source": "spoonacular", "recipe_id": 7}]
