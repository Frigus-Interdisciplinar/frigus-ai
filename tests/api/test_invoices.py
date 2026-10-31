import pytest
from fastapi.testclient import TestClient

from frigus_ai.api.app import app
from frigus_ai.api.auth import get_current_user
from frigus_ai.api.routes.v1 import invoices
from frigus_ai.schemas.invoice import InvoiceExtraction


@pytest.fixture
def cliente():
    app.dependency_overrides[get_current_user] = lambda: "user-1"
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_extract_recebe_lista_produtos_e_devolve_produtos_classificados(cliente, monkeypatch):
    class Extractor:
        async def ainvoke(self, messages):
            assert "PRODUTOS" in messages[1].content
            return InvoiceExtraction(
                items=[{"lineNumber": 1, "description": "LEITE INTEGRAL 1L", "productName": "Leite integral", "brand": None,
                        "quantity": 2, "unit": "UN", "unitOfMeasure": "UNIT", "unitPrice": 5.0,
                        "totalPrice": 10.0, "category": "DAIRY", "storagePlace": "FRIDGE", "confidence": 0.98,
                        "evidence": "LEITE INTEGRAL 1L 2 UN"}],
                warnings=[],
            )

    monkeypatch.setattr(invoices, "_extractor", Extractor())
    response = cliente.post("/v1/invoices/extract", json={
        "documentType": "NFCE", "state": "SP", "locale": "pt-BR",
        "products": [{"lineNumber": 1, "description": "LEITE INTEGRAL 1L", "quantity": 2, "unit": "UN",
                       "unitPrice": 5, "totalPrice": 10, "evidence": "LEITE INTEGRAL 1L 2 UN"}],
    })

    assert response.status_code == 200
    assert response.json()["items"][0]["category"] == "DAIRY"
    assert response.json()["items"][0]["productName"] == "Leite integral"
    assert response.json()["items"][0]["evidence"] == "LEITE INTEGRAL 1L 2 UN"


def test_extract_rejeita_contrato_antigo_sem_lista_de_produtos(cliente):
    response = cliente.post("/v1/invoices/extract", json={
        "documentType": "NFCE", "state": "SP", "pageText": "texto antigo",
    })
    assert response.status_code == 422
