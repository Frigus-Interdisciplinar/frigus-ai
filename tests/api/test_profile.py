"""Contrato HTTP de `/v1/profile`. `user_service` vira stub — o merge/segurança de
alergias já tem teste próprio em tests/services/test_user_service.py."""

import pytest
from fastapi.testclient import TestClient

from frigus_ai.api.app import app
from frigus_ai.domain.models import Fatos, RecipePreferences
from frigus_ai.services.user_service import user_service


@pytest.fixture
def cliente(monkeypatch):
    async def _obter_ou_criar_padrao():
        return "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"

    monkeypatch.setattr(user_service, "obter_ou_criar_padrao", _obter_ou_criar_padrao)

    return TestClient(app, raise_server_exceptions=False)


def test_get_profile_devolve_fatos_do_usuario(cliente, monkeypatch):
    async def _buscar_fatos(user_id):
        assert user_id == "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"
        return Fatos(alergias=["lactose"], preferencias=["frango"])

    monkeypatch.setattr(user_service, "buscar_fatos", _buscar_fatos)

    r = cliente.get("/v1/profile")

    assert r.status_code == 200
    assert r.json() == {
        "alergias": ["lactose"],
        "preferencias": ["frango"],
        "restricoes": [],
        "habitos": [],
    }


def test_put_profile_pode_remover_alergia(cliente, monkeypatch):
    salvos = []

    async def _sobrescrever_fatos(user_id, fatos):
        salvos.append((user_id, fatos))

    monkeypatch.setattr(user_service, "sobrescrever_fatos", _sobrescrever_fatos)

    r = cliente.put("/v1/profile", json={"alergias": [], "preferencias": ["frango"]})

    assert r.status_code == 200
    assert r.json()["alergias"] == []
    assert salvos == [("3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", Fatos(alergias=[], preferencias=["frango"]))]


def test_patch_preferencias_de_receitas_e_parcial_e_normaliza_restricao(cliente, monkeypatch):
    recebidos = []

    async def _atualizar(user_id, patch):
        recebidos.append(patch)
        return RecipePreferences(restricoes=patch.restricoes or [], preferir_rapidas=True)

    monkeypatch.setattr(user_service, "atualizar_preferencias_receitas", _atualizar)

    r = cliente.patch("/v1/profile/recipe-preferences", json={"restricoes": ["vegetariano"]})

    assert r.status_code == 200
    assert r.json()["restricoes"] == ["Vegetariano"]
    assert recebidos[0].preferir_rapidas is None
    assert recebidos[0].restricoes == ["Vegetariano"]


def test_patch_preferencias_rejeita_campo_desconhecido(cliente):
    r = cliente.patch("/v1/profile/recipe-preferences", json={"alergias": ["x"]})

    assert r.status_code == 422
