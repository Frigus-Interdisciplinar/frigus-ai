"""
O que importa testar aqui não é o protocolo MCP (é do SDK), e sim a parte que é
nossa: as 18 tools ficarem expostas e a identidade do `X-API-Key` chegar dentro da
tool via contextvar — se o `session_context` não atravessar o middleware ASGI, as
tools de Postgres levantam RuntimeError em produção e ninguém percebe aqui.
"""

import json

import pytest
from fastapi.testclient import TestClient

from frigus_ai.tools.postgres.context import current_stock_id, current_user_id
from interfaces.api import auth
from interfaces.api.main import app
from interfaces.mcp import server as mcp_server

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


@pytest.fixture(scope="module")
def cliente():
    """
    Escopo de módulo porque o gerenciador de sessão do SDK só aceita um `run()` por
    instância, e o app do MCP é único no processo — um TestClient por teste tentaria
    subir o lifespan duas vezes.
    """

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(auth.settings, "API_KEY_AUTH_ENABLED", True)
        mp.setattr(auth, "get_user_id_by_api_key", lambda key: 42 if key == "boa" else None)
        mp.setattr(mcp_server, "resolver_stock_id", lambda user_id: 99)

        # base_url com host:porta porque o SDK liga proteção contra DNS rebinding por
        # padrão e o allowlist é `localhost:*` — o "testserver" do TestClient dá 421.
        with TestClient(app, base_url="http://localhost:8000") as client:
            yield client


def _chamar(cliente, metodo: str, params: dict | None = None, key: str = "boa"):
    return cliente.post(
        "/mcp/",
        headers={**_HEADERS, "X-API-Key": key},
        json={"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params or {}},
    )


def _resultado(resposta):
    """A resposta vem como SSE (`data: {...}`) ou JSON puro, dependendo do Accept."""

    corpo = resposta.text
    if "data:" in corpo:
        corpo = corpo.split("data:", 1)[1].strip().splitlines()[0]
    return json.loads(corpo)["result"]


def test_lista_as_tools_de_dominio(cliente):
    r = _chamar(cliente, "tools/list")

    assert r.status_code == 200
    nomes = {t["name"] for t in _resultado(r)["tools"]}
    assert {"query_stock", "mark_purchased", "faq_retriever", "gastos_mensais"} <= nomes
    assert len(nomes) == len(mcp_server.TOOLS)


def test_schema_da_tool_vem_dos_parametros_reais(cliente):
    """
    O adaptador embrulha a tool do LangChain; se o `functools.wraps` não repassasse a
    assinatura original, o MCP publicaria uma tool de um argumento só (`kwargs`) e
    nenhum host conseguiria chamá-la.
    """

    tools = {t["name"]: t for t in _resultado(_chamar(cliente, "tools/list"))["tools"]}
    propriedades = tools["query_stock"]["inputSchema"]["properties"]

    assert "kwargs" not in propriedades
    assert {"product_name", "storage_place", "vencendo_em_dias"} <= set(propriedades)


def test_sem_api_key_valida_nao_passa(cliente):
    assert _chamar(cliente, "tools/list", key="ruim").status_code == 401


def test_identidade_do_header_chega_dentro_da_tool(cliente):
    """
    As tools de Postgres leem user_id/stock_id de contextvar, nunca dos argumentos —
    o middleware ASGI é quem preenche. Este teste falha se essa ponte quebrar.
    """

    visto = {}

    def _espiao(nota: str = "") -> dict:
        visto["user_id"] = current_user_id()
        visto["stock_id"] = current_stock_id()
        return {"status": "ok"}

    mcp_server.servidor.tool(name="espiao")(_espiao)

    try:
        r = _chamar(cliente, "tools/call", {"name": "espiao", "arguments": {}})

        assert r.status_code == 200
        assert visto == {"user_id": 42, "stock_id": 99}

    finally:
        del mcp_server.servidor._tool_manager._tools["espiao"]
