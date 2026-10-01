from fastapi.testclient import TestClient
from pydantic import SecretStr

from frigus_ai.api import app as app_mod
from frigus_ai.api.routes import metrics as metrics_mod

client = TestClient(app_mod.app)


def test_metrics_aberto_sem_token():
    assert client.get("/metrics").status_code == 200


def test_metrics_com_token_exige_bearer(monkeypatch):
    monkeypatch.setattr(metrics_mod.settings.api_keys, "metrics_token", SecretStr("s3gredo"))

    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3gredo"}).status_code == 200
