# MCP (SDK oficial `mcp`)

Pegadinhas reais encontradas ao montar `interfaces/mcp/server.py` — o servidor MCP que expõe as
tools de domínio em `POST /mcp`, montado dentro da API FastAPI. Consulte antes de mexer nele.

## `mcp` 2.x renomeou `FastMCP` para `MCPServer`

Todo tutorial e todo código de `mcp<2` usa `from mcp.server.fastmcp import FastMCP`. Nesta versão o
módulo existe só para levantar `ModuleNotFoundError` com a mensagem de migração.

```python
from mcp.server.mcpserver import MCPServer

servidor = MCPServer(name="frigus-ai")
```

`stateless_http` **não** é argumento do construtor (o erro é `unexpected keyword argument`) — é do
`streamable_http_app()`.

## Lifespan de app montado não roda sozinho

`app.mount("/mcp", ...)` registra as rotas, mas o FastAPI **não** executa o lifespan do sub-app. O
gerenciador de sessão do SDK só inicializa o task group dentro do próprio lifespan, então sem
encadear toda chamada morre em `RuntimeError: Task group is not initialized`.

Do this — encadeia no lifespan do app principal:

```python
# interfaces/mcp/server.py
_app_mcp = servidor.streamable_http_app(streamable_http_path="/", stateless_http=True)


def lifespan_mcp():
    return _app_mcp.router.lifespan_context(_app_mcp)


# interfaces/api/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_mcp():
        yield
```

Instead of:

```python
# DO NOT DO THIS — as rotas respondem, mas toda tools/call estoura
app.mount("/mcp", servidor.streamable_http_app())
```

**No teste:** `TestClient(app)` só roda o lifespan quando usado como context manager
(`with TestClient(app) as client`). E o gerenciador de sessão aceita **um** `run()` por instância —
como o app do MCP é único no processo, a fixture do TestClient precisa ser de escopo de módulo, ou o
segundo teste quebra com "can only be called once per instance".

## `stateless_http=True` é o que mantém o `session_context` válido

As tools de Postgres leem `user_id`/`stock_id` de `contextvars` (`tools/postgres/context.py`), e app
montado não executa dependência do FastAPI — quem preenche isso é um middleware ASGI. Com sessão MCP
de longa duração o handler roda em **outra task**, e o contextvar aberto no middleware não chega na
tool. Em modo stateless cada request se resolve dentro da própria chamada.

`tests/interfaces/mcp/test_server.py` tem um teste que registra uma tool-espiã e afirma que
`current_user_id()`/`current_stock_id()` chegam corretos — é o que trava essa regressão.

## Proteção contra DNS rebinding: 421 fora do localhost

`streamable_http_app()` tem `host="127.0.0.1"` por default e, para localhost, liga a proteção com
allowlist `["127.0.0.1:*", "localhost:*", "[::1]:*"]`. Consequências:

- Em teste, o `base_url` do `TestClient` precisa ser `http://localhost:8000` — o default
  `http://testserver` responde **421 Misdirected Request**.
- Em deploy com domínio real, é preciso passar `host=` diferente de localhost (o que desliga a
  proteção automática) ou um `TransportSecuritySettings` próprio. Senão **tudo** responde 421.

## Adaptar tool do LangChain: `functools.wraps` não é cosmético

O SDK deriva o JSON Schema da tool da **assinatura** da função (`inspect.signature`), não de um
`args_schema`. Ao embrulhar uma tool do LangChain:

```python
def _adaptar(tool):
    @functools.wraps(tool.func)      # __wrapped__: é o que faz inspect.signature ver os params reais
    def wrapper(**kwargs):
        return tool.invoke(kwargs)   # invoke, não tool.func: roda o args_schema (validators inclusos)
    return wrapper
```

Sem o `wraps`, o `**kwargs` vira um único parâmetro obrigatório chamado `kwargs` e a chamada falha
com `1 validation error: kwargs Field required` — a tool aparece no `tools/list` e é impossível de
chamar. `tests/interfaces/mcp/test_server.py::test_schema_da_tool_vem_dos_parametros_reais` trava isso.

**Limitação aceita:** a descrição por campo vive no `args_schema` do LangChain e o SDK não a lê, então
o schema publicado sai sem ela. A descrição da tool (docstring), que é o que guia o host, é preservada.
