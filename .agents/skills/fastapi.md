# FastAPI

Duas partes: **práticas oficiais** (do skill oficial do FastAPI) e **pegadinhas deste repo**
(achados reais, conforme forem aparecendo). Consulte antes de mexer em `interfaces/api/`.

## Referências

O conteúdo longo do skill oficial está nos arquivos ao lado, neste mesmo diretório:

| Arquivo | Assunto |
|---|---|
| [dependencies.md](dependencies.md) | `Depends` com `yield`, `scope`, dependência como classe |
| [responses.md](responses.md) | return type vs. `response_model`, status code, headers |
| [streaming.md](streaming.md) | JSON Lines, SSE (`EventSourceResponse`), bytes |
| [path-operations.md](path-operations.md) | roteamento, `APIRouter`, parâmetros de rota |
| [pydantic.md](pydantic.md) | Ellipsis, `RootModel`, validação |
| [other-tools.md](other-tools.md) | uv, Ruff, ty, Asyncer, SQLModel, HTTPX |

Os arquivos oficiais linkam entre si como `references/<arquivo>.md`; aqui todos estão no mesmo
diretório, então o caminho é só `<arquivo>.md`.

## Divergências deliberadas do skill oficial

O skill oficial recomenda algumas coisas que **não** se aplicam aqui. Não "corrija" o repo pra
segui-las sem discutir antes:

- **SQLModel:** o oficial prefere SQLModel a SQLAlchemy. Aqui o Postgres é acessado via `psycopg2`
  cru (schema `dataload` fornecido pela disciplina, DDL em `data/sql/schema.sql`, sem ORM nenhum) —
  não é o caso de escolher entre SQLModel e SQLAlchemy, nenhum dos dois se aplica.
- **Rotas `async`:** ~~aqui rota é `def` normal de propósito~~ — **essa divergência deixou de valer
  na Fase 2 do async.** Hoje as rotas são `async def` e convergem com o skill oficial. O I/O
  síncrono (psycopg2, pymongo) não sumiu: ele é embrulhado em `asyncio.to_thread` na camada de
  repositories (`chat/repositories.py`), e o grafo é dirigido por `ainvoke`. A regra que continua
  valendo é a de sempre: **nada de I/O bloqueante direto dentro de `async def`** — se for síncrono,
  vai pra thread antes.
- **Asyncer:** não é dependência do projeto. Só faz sentido se aparecer código de fato async (ex.
  streaming SSE) que precise chamar o grafo síncrono — aí sim avalie, não antes.
- **HTTPX:** ~~ainda não é dependência aqui~~ — já é. `tools/spoonacular/connection.py` usa
  `httpx.Client`, e o `TestClient` do FastAPI depende dele. Segue sendo a escolha padrão pra client
  HTTP novo, em vez de `requests`.

## Usar `Annotated` em dependência e parâmetro

Prefira `Annotated[T, Depends(...)]` / `Annotated[T, Security(...)]` ao valor default. Mantém a
assinatura da função utilizável fora do FastAPI (teste chama direto), respeita o tipo e permite
reaproveitar a dependência como alias.

Do this — alias de tipo reaproveitável, declarado uma vez ao lado da dependência:

```python
# interfaces/api/auth.py (exemplo — mecanismo de auth ainda não decidido aqui)
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key")


def get_current_user(api_key: Annotated[str, Security(_api_key_header)]) -> str:
    ...


CurrentUserDep = Annotated[str, Depends(get_current_user)]
```

```python
# interfaces/api/routes/chats.py
@router.post("/{chat_id}/messages")
def send_message(chat_id: str, payload: MessageCreate, user_id: CurrentUserDep):
    ...
```

Instead of:

```python
# DO NOT DO THIS
def get_current_user(api_key: str = Security(_api_key_header)) -> str: ...


def send_message(chat_id: str, user_id: str = Depends(get_current_user)): ...
```

## Return type em vez de `response_model` quando são a mesma coisa

Se a rota devolve exatamente o modelo, anote o retorno e apague o `response_model` — a anotação já
valida, filtra, documenta e serializa (com a serialização do Pydantic em Rust).

Do this:

```python
@router.post("", status_code=status.HTTP_201_CREATED)
def create_chat(user_id: CurrentUserDep) -> ChatCreateResponse:
    return ChatCreateResponse(chat_id=chat_service.create_chat(user_id))
```

Instead of:

```python
# DO NOT DO THIS — response_model duplicando o que a anotação de retorno já diria
@router.post("", response_model=ChatCreateResponse, status_code=status.HTTP_201_CREATED)
def create_chat(user_id=Depends(get_current_user)):
    return ChatCreateResponse(chat_id=...)
```

`response_model` continua certo quando o schema público é **diferente** do que a função retorna. Ver
[responses.md](responses.md).

## Nada de Ellipsis (`...`) nos schemas

`Field(..., min_length=1)` é forma antiga: campo sem default já é obrigatório.

Do this:

```python
class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
```

Instead of:

```python
# DO NOT DO THIS
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
```

Mesma regra pra `Query()`/`Path()`/`Body()`. E não use `RootModel`: pra body que é lista, anote
`Annotated[list[Item], Body()]` direto. Ver [pydantic.md](pydantic.md).

## Parâmetros no `APIRouter`, não no `include_router()`

`prefix`, `tags` e dependências compartilhadas ficam no próprio router:

```python
router = APIRouter(prefix="/v1/chats", tags=["chats"])
```

`interfaces/api/main.py` então só faz `app.include_router(chats_router)`, sem repetir configuração.
Uma operação HTTP por função — não misture `GET` e `POST` no mesmo handler.

## Serialização: sem `ORJSONResponse`/`UJSONResponse`

Estão deprecados. A performance vem de declarar o tipo de retorno / `response_model` e deixar o
Pydantic serializar.

## Streaming / SSE

SSE é `response_class=EventSourceResponse` + `yield`:

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent


@router.post("/{chat_id}/messages/stream", response_class=EventSourceResponse)
async def stream_message(...) -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(data={"status": "pensando"}, event="status")
```

**Cuidado ao chegar aqui:** `chat.service.send_message` já é `async` (Fase 2), então o endpoint SSE
pode chamá-lo direto — o cuidado mudou de lugar. Pra streaming de token o grafo tem que ser dirigido
por `fluxo_agentes().astream(..., stream_mode="messages")`, que devolve 2-tuplas
`(AIMessageChunk, metadata)`. **Todos os 10 nós têm LLM**, então isso inclui o `ROUTE=` do roteador,
o veredito do Juiz e o guardrail: filtre por `metadata["langgraph_node"]` ou o cliente recebe o
raciocínio interno inteiro. Ver [streaming.md](streaming.md).

---

# Pegadinhas deste repo

## `except Exception` genérico em rota engole exceção de domínio e vaza erro interno

`routes/chats.py:send_message` tinha um único `except Exception` que virava
`HTTPException(500, str(e))`. Dois problemas de uma vez:

1. `LimiteDeMensagensExcedido` (rate limit do Redis, `chat/service.py`) caía nele — o cliente
   recebia **500** onde o certo é **429 + `Retry-After`**. O limite funcionava; a API mentia sobre ele.
2. `str(e)` num erro de infra devolve a mensagem crua do psycopg2/pymongo pro cliente HTTP
   (usuário, senha, fragmento de query). O traceback, que era o que interessava, ia pro lixo.

Regra: capture as exceções de domínio **antes** do `except Exception`, e no genérico use
`logger.exception(...)` + mensagem fixa no `detail`. Nunca `str(e)` de exceção não prevista no body.

## `Role` do domínio shadowando `Role` do schema quebrava o import da API inteira

`schemas/chat.py` fazia `from frigus_ai.chat.models import Role` **e** `... import Role as
DomainRole`, e montava `_ROLE_MAP = {DomainRole.HUMAN: Role.USER, ...}` **acima** da declaração do
`class Role(StrEnum)` local. Nesse ponto `Role` ainda era o do domínio (`HUMAN`/`AI`), então
`Role.USER` levantava `AttributeError` no import do módulo — `uvicorn interfaces.api.main:app` não
subia de jeito nenhum.

Passou despercebido porque **não havia nenhum teste que importasse `interfaces.api.main`**. Hoje há
(`tests/interfaces/api/test_chats.py`). Ao criar schema que traduz enum de domínio pra enum público:
importe o de domínio só com alias, declare o público primeiro, monte o mapa depois.
