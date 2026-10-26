"""Preferências de receitas: PATCH grava só os campos enviados, em subdocumento próprio."""

import frigus_ai.repositories.fatos_repository as repo
from frigus_ai.domain.models import RecipePreferencesPatch


class _FakeCollection:
    def __init__(self, doc=None):
        self.doc = doc
        self.updates = []

    def find_one(self, filtro, projecao=None):
        return self.doc

    def update_one(self, filtro, update, upsert=False):
        self.updates.append((filtro, update, upsert))


def test_patch_grava_so_campos_enviados_inclusive_lista_vazia(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(repo, "collection", fake)

    repo.atualizar_preferencias_receitas("u1", RecipePreferencesPatch(restricoes=[], preferir_rapidas=True))

    filtro, update, upsert = fake.updates[0]
    assert filtro == {"user_id": "u1"} and upsert is True
    assert update["$set"]["recipe_preferences.restricoes"] == []
    assert update["$set"]["recipe_preferences.preferir_rapidas"] is True
    assert "recipe_preferences.preferir_economicas" not in update["$set"]


def test_patch_vazio_nao_escreve(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(repo, "collection", fake)

    repo.atualizar_preferencias_receitas("u1", RecipePreferencesPatch())

    assert fake.updates == []


def test_sem_documento_devolve_padrao(monkeypatch):
    monkeypatch.setattr(repo, "collection", _FakeCollection(doc=None))

    prefs = repo.buscar_preferencias_receitas("u1")

    assert prefs.restricoes == [] and prefs.preferir_rapidas is False
