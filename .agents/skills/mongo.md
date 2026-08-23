# MongoDB (pymongo + MongoDBSaver)

Mongo guarda três coisas aqui: histórico de conversa (`tools/mongo/chats`), perfil de usuário
(`tools/mongo/users`) e o checkpoint do LangGraph (`graph/builder.py`).

## `MongoClient` é lazy, `MongoDBSaver` não é — já resolvido aqui, mantenha assim

`MongoClient(...)` **não** abre socket no construtor — só na primeira operação. É por isso que
`banco = _conectar()` no escopo de módulo (`tools/mongo/connection.py`) não viola a regra de "sem
I/O no import" e pode ser importado à vontade.

`MongoDBSaver.__init__`, ao contrário, **conecta na hora**: ele cria índices nas collections de
checkpoint. Instanciar no import faria todo `python main.py`, todo `pytest` e toda coleta de teste
baterem no Mongo antes de qualquer coisa acontecer — por isso `fluxo_agentes()` em
`graph/builder.py` é `@functools.cache` numa função, não uma variável de módulo:

```python
@functools.cache
def fluxo_agentes():
    checkpointer = MongoDBSaver(
        banco.client,
        db_name=banco.name,
        checkpoint_collection_name="graph_checkpoints",
        writes_collection_name="graph_checkpoint_writes",
    )
    return grafo.compile(checkpointer=checkpointer)
```

`@cache` (stdlib) já dá o singleton lazy — não escreva memoização na mão com `if _instancia is None`.

## `ServerSelectionTimeoutError` em deploy hospedado = allowlist do host, não código

Achado do assessor-ai (repo irmão, mesmo stack de Mongo) — vale saber antes de deployar este projeto
em algo diferente de localhost:

- erro em **todos** os shards do cluster ao mesmo tempo (`ServerSelectionTimeoutError`, às vezes com
  `TLSV1_ALERT_INTERNAL_ERROR` junto — o alerta de TLS é consequência, não causa)
- funciona local, quebra só no ambiente hospedado
- nada mudou no código de conexão entre o deploy que funcionava e o que quebrou

Antes de mexer em versão de lib, versão de Python ou parâmetro de TLS: confira se o egress do host
de deploy está liberado no allowlist do provedor de Mongo (Atlas ou equivalente) — hosts com IP
dinâmico (ex. FastAPI Cloud) não são cobertos por allowlist fixa de IP.

## O pin `pymongo>=4.12,<4.17` não é decoração

Quem trava o teto é o `langgraph-checkpoint-mongodb` (a versão estável exige `pymongo<4.17`). Subir
o pymongo sem subir o checkpointer quebra o grafo inteiro, não só o Mongo. Se um PR do Dependabot
tentar passar disso, confira a versão do `langgraph-checkpoint-mongodb` antes de mergear.

## Histórico curto: `$slice` na projeção — já é assim em `tools/mongo/chats/core.py:buscar`

O documento de chat acumula todas as mensagens da sessão num array. Buscar o documento inteiro pra
usar as últimas N traz o histórico completo pela rede a cada turno; `buscar()` já usa `$slice` pro
servidor devolver só o final:

```python
return collection.find_one(
    {"session_id": session_id},
    {"messages": {"$slice": -limit}},
)
```

Ao adicionar uma busca nova sobre `chats`/`users`, siga o mesmo padrão em vez de trazer o array
inteiro e fatiar em Python.

## Filtro por `user_id` na query — gap real aqui, não só teoria

`buscar()` em `tools/mongo/chats/core.py` filtra só por `session_id`, sem `user_id` no filtro —
diferente da regra que as tools de Postgres seguem (escopo por `user_id`/`stock_id` via
`tools/postgres/context.py`, nunca checado depois de trazer o dado). Checar dono **depois** de
buscar o documento é IDOR esperando acontecer; hoje `buscar()` nem faz essa checagem depois, então
qualquer `session_id` válido devolve o histórico de qualquer usuário. Vale corrigir antes de expor
isso via API (a exposição atual é só terminal local, onde `session_id` não vaza).
