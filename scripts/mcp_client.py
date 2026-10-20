"""
Cliente MCP de verdade (SDK oficial) contra a API rodando: initialize, list_tools e call_tool.

Uso: `python scripts/mcp_client.py [url] [tool]` com a API no ar (`just run api`). A chave vem de
`FRIGUS_API_KEY` (omitida, só funciona com `API__KEY_AUTH_ENABLED` desligado).
"""

import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client


async def main(url: str, tool: str) -> None:
    headers = {"X-API-Key": os.environ["FRIGUS_API_KEY"]} if "FRIGUS_API_KEY" in os.environ else {}

    async with streamable_http_client(url, http_client=create_mcp_http_client(headers=headers)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"{len(tools)} tools: {', '.join(t.name for t in tools)}")

            resultado = await session.call_tool(tool, {})
            print(f"\n{tool} -> isError={resultado.is_error}")
            print(resultado.content[0].text[:500])


if __name__ == "__main__":
    asyncio.run(main(*(sys.argv[1:3] or ["http://localhost:8000/mcp/"]), *(["query_stock"] if len(sys.argv) < 3 else [])))
