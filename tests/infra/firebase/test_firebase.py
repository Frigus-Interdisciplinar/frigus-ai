"""Login do app Frigus: validar o ID token só precisa do ID do projeto, sem service account."""

import pytest

from frigus_ai.api.auth.dependencies import _usuario_do_firebase
from frigus_ai.infra.firebase import firebase, get_firebase_app
from frigus_ai.settings import settings


@pytest.fixture
def so_com_id_do_projeto(monkeypatch):
    monkeypatch.setattr(settings.api_keys, "firebase_project_id", "projeto-teste")
    monkeypatch.setattr(settings.api_keys, "firebase_credentials_path", "")
    firebase.fechar()
    yield
    firebase.fechar()


def test_inicia_so_com_o_id_do_projeto(so_com_id_do_projeto):
    assert get_firebase_app().project_id == "projeto-teste"


def test_token_invalido_vira_none_e_nao_500(so_com_id_do_projeto):
    """Regressão: o `except` citava `firebase_auth.AuthError`, que não existe, e todo token inválido
    estourava `AttributeError` (500) em vez de virar 401."""

    assert _usuario_do_firebase("isso-nao-e-um-token") is None
