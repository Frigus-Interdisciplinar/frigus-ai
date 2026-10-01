# Refactor unificado (hardening da API, config, domain, grafo)

Origem: plano unificado de 30/09/2026 (5 fases) + proposta de settings agrupado (abaixo).
Branch de trabalho: `fix/hardening-api-fase1`.

## Status (30/09/2026)

| Item | Estado | Onde |
|---|---|---|
| 1.1 auth obrigatória em production | feito | `settings.py` (validator) |
| 1.2 / 1.3 erros sem `str(exc)`, metadata na exceção | feito | `exceptions.py`, `api/exception_handler.py` |
| 1.4 `request_id` | feito (500 não tratado não leva o header, só o corpo) | `api/middleware.py`, `logging.py` |
| 1.5 ApiKeyService atômico (Lua) | feito, **falta testar contra Redis real** | `services/api_key_service.py` |
| 1.6 HMAC, revoke, rotate | pendente (baixa prioridade) | — |
| 1.7 CORS/fail-open por ambiente | feito; `guard` segue criado no import (decora rotas); sem métrica `unmatched` | `api/middleware.py` |
| 36 settings agrupado | feito | `settings/` |
| 3.1 código morto (`graph/llm.py`, `Repository`, `ServiceError`) | feito | — |
| 3.2 / 3.3 `domain/models.py`, `domain/types.py`, `domain/identifiers.py` | feito | `domain/` |
| 2.1–2.4 `models.py` dividido | feito (sem `LLMSettings` aninhada, `build_llm` lê o settings global) | `settings/llm.py`, `infra/llm/` |
| 2.2 limites do grafo no settings | feito, variáveis planas `MAX_HISTORICO_MENSAGENS` e `MAX_TENTATIVAS_JUIZ` | `settings.py` |
| 2.5 LLMs lazy | descartado por ora (criar cliente não faz rede; 6 consumidores mudariam) | — |
| Fase 4, Fase 5, restante da Fase 3 | pendente | — |

Decisão: `Environment` só aceita `local` e `production` (sem `test`/`staging`).

## Item 36 — Settings agrupado em modelos aninhados (FEITO em 30/09/2026)

Implementado como pacote `src/frigus_ai/settings/` (`base.py` com o `Settings` + `api.py`, `api_keys.py`, `database.py`, `llm.py`, `observability.py`; `__init__` reexporta `settings`). o enum `Model` mora em `settings/llm.py` (a pasta `config/` foi removida). Grupos: `api`, `database`, `api_keys`, `llm`, `observability`; `environment` fica no topo (grupo de um campo só não vale). `SIGNUP_SECRET` continua opcional. Env vars viram `GRUPO__CAMPO` — `.env`, `.env.example`, README, CI (`OBSERVABILITY__LANGSMITH_*`) e conftest já migrados; **deploy/secrets externos precisam ser renomeados**. `.env` antigo (nomes planos) falha no boot com "Field required".

Proposta original, para referência:

PR/commit **isolado**: muda nomes de env var, `.env`, docker-compose, CI e deploy. Não misturar com
outras mudanças. Substitui a `LLMSettings` solta do item 2.2 (vira o grupo `llm`).

### Forma

- Um único `Settings(BaseSettings)` como ponto de entrada e um único singleton `settings`.
- Subgrupos como `BaseModel` (não `BaseSettings` por arquivo).
- `env_nested_delimiter="__"`, `case_sensitive=False`, `extra="ignore"`.
- Credenciais sempre `SecretStr` (`repr`/log não vaza); `.get_secret_value()` só ao entregar ao SDK.
- Validação de production nos validators (hoje: auth ligada, CORS sem `"*"`).
- Código em `config/` (`settings.py` + um arquivo por grupo), como na estrutura-alvo.

### Grupos

| Grupo | Conteúdo | Hoje (plano) |
|---|---|---|
| `api` | CORS, reload, host/port, prefixo, limites de payload, rate limit | `API_RELOAD`, `API_CORS_ORIGINS`, `API_KEY_AUTH_ENABLED` |
| `database` | Postgres, Mongo, Redis, Neo4j, Qdrant (URLs, pool, timeout) | `POSTGRES_URI`, `MONGODB_URI`, `REDIS_URL`, `NEO4J_URI`, `QDRANT_*` |
| `api_keys` | tokens/segredos de autenticação e keys de serviços externos | `SIGNUP_SECRET`, `METRICS_TOKEN`, keys de provider |
| `llm` | keys de provider, modelo padrão, temperaturas, limites do grafo | `*_API_KEY`, `MAX_HISTORICO_MENSAGENS`, `MAX_TENTATIVAS_JUIZ` |
| `observability` | LangSmith, Prometheus, nível de log | `LANGSMITH_*`, `PROMETHEUS_URL` |
| `runtime` | `environment` (`local`/`production`), debug | `ENVIRONMENT` |

Não criar grupo "misc". Regra de negócio (limites de chat/compras) não mistura com config técnica:
ou um grupo `limits`, ou perto do domínio.

### Exemplo de `.env` depois

```env
ENVIRONMENT=production            # ou RUNTIME__ENVIRONMENT, ver pendência abaixo
DATABASE__POSTGRES_URI=postgresql+psycopg2://...
DATABASE__REDIS_URL=redis://...
API_KEYS__SIGNUP_SECRET=...
API__CORS_ORIGINS=["https://app.exemplo.com"]
LLM__GEMINI_API_KEY=...
LLM__MAX_HISTORICO_MENSAGENS=21
```

### Cuidados (o exemplo de origem tinha estes deslizes)

- Manter os nomes atuais de campo onde existirem (`REDIS_URL`, não `redis_uri`); renomear só se
  houver motivo.
- `Environment` fica só com `local` e `production` (o exemplo de origem listava 4 valores).
- `SIGNUP_SECRET` hoje é opcional (`""`); no exemplo vira obrigatório. Decidir antes de copiar.
- Obrigatórios sem default dentro de modelos aninhados falham só quando o grupo inteiro falta;
  testar mensagem de erro com `.env` incompleto.
- Os testes recarregam `frigus_ai.settings` com `importlib.reload` (ex.: `tests/graph/test_llm.py`);
  `tests/conftest.py` seta env plano com `setdefault`. Os dois precisam migrar para o `__`.
- Transição opcional: manter propriedades com os nomes antigos (`settings.POSTGRES_URI`) por um
  tempo, só se ficar caro trocar todos os consumidores de uma vez. Preferência: migrar de vez.

### Passos

1. Mapear consumidores: `grep -rn "settings\." src tests` (e `Settings(` em testes).
2. Criar `config/settings.py` + grupos, mantendo `frigus_ai.settings` reexportando `settings`.
3. Trocar consumidores por grupo, um grupo por commit.
4. Atualizar `.env.example`, `docker-compose`, CI (`.github/workflows/ci.yml`), README e AGENTS.md.
5. Avisar quem faz deploy: todas as env vars mudam de nome.

## Atualização — plano de 7 fases (30/09/2026)

Feito além da tabela acima: 0.x; 1.1 a 1.5 (1.3 com `DomainError`; 1.4 com `unknown` + `frigus_http_unmatched_total`);
2.1, 2.2, 2.4, 2.5, 2.6; 3.1, 3.2 (parcial); 4.1 a 4.6; 5.1 a 5.4; 6.1 a 6.5.

- 2.4/6.1: `fatos` (dict) e `conversas_anteriores` (list) vão no estado, pré-carregados pelo
  runner (`_carregar_contexto`) e entregues ao agente por `context=ContextoPrompt` →
  `request.runtime.context` no `dynamic_prompt`. A ContextVar `conversas_anteriores` foi removida.
- 6.2: `_criar_checkpointer()` faz `ping` (timeout 5s); `MemorySaver` só em `local`, production falha alto.
- 6.3: só ampliei o regex ("composição corporal", "índice glicêmico"); o LLM já revisa sempre que há match.
- 6.5: `tests/graph/test_thread_id.py` mostra que o `thread_id` chega ao agente interno por herança
  (dois chats concorrentes não misturam checkpoint).
- Mudança de URL: `/v1/keys` → `/keys` (auth fora do versionamento, como no plano).

Ainda pendente / descartado:
- 2.3 LLMs lazy: descartado (agentes e `with_structured_output` também teriam que virar lazy; ganho pequeno).
- 1.4: guard como factory (decora rotas no import).
- 3.2: feito (`infra/llm/` pasta, `build_llm(model, temperature, llm_settings)`, embedding e temperaturas no `settings.llm`); `default_model` não criado (sem uso).
  `qdrant/connection.py` ainda usa `Model.EMBEDDING_MODEL`.
- 3.1 divergências (`config/` vs `settings/`, `secrets` vs `api_keys`, grupo `runtime`): ver decisão do usuário.
- Fase 7 (logging, HMAC, revoke/rotate, contrato das tools).
- Falta testar o script Lua do `AuthService` contra um Redis real.

## Atualização — Fase 7 (30/09/2026)

- HMAC das API keys: `API_KEYS__HASH_SECRET` (opcional; vazio = SHA-256 puro). Ligar/trocar invalida
  todas as keys já emitidas.
- Revoke/rotate: `AuthService.revoke_api_key` / `rotate_api_key` (scripts Lua atômicos) e rotas
  `DELETE /keys` e `POST /keys/rotate` (autenticadas pela key atual). Scripts ainda sem teste contra Redis real.
- Contrato das tools: já tipado (`ToolResponse`); agora documentado no `OBRIGATORIEDADE_TOOLS` do prompt.
  `StructuredTool` não tem `response_schema`, então o contrato vai por texto.
- Fica de fora (backlog real): separar `logging.py` (só quando crescer), guard como factory (1.4), LLMs lazy (2.3).

## Atualização — organização final (01/10/2026)

- `config/` removida: `Model` agora vive em `settings/llm.py`.
- `logging.py` virou o pacote `infra/logging/` (`setup.py`, `decorators.py`); `Logging` segue como fachada em `__init__`.
- `api/middleware.py` virou `api/middleware/{request_id,metrics,security}.py`; `api/exception_handler.py` virou
  `api/errors/handlers.py` e `ErrorResponse` foi para `api/errors/responses.py`.
- `ErrorCode` mudou para `domain/errors.py` (o domínio não importa mais de `schemas/`); `schemas/errors.py` removido.
- Ainda não revisado: README tem uma árvore de estrutura antiga (cita `config/` com docker/logging e `interfaces/`).
