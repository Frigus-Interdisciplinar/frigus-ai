# Migração A2A SDK

## Feito

- Dependência `a2a-sdk[fastapi]` adicionada.
- Agent Card, `DefaultRequestHandler`, `InMemoryTaskStore` e executor criados.
- Rotas A2A registradas pelo app.

## Falta fazer

- Ajustar testes e payloads para o contrato atual do SDK (`SendMessage`).
- Propagar `X-API-Key` ao `ServerCallContext`.
- Remover o uso fixo de `DEMO_USER_ID`.
- A estrutura do mapa de sessões foi tipada e o lock ganhou double-check; a sessão ainda é local
  ao processo e precisa ser persistida antes de produção/múltiplos workers.
- Evitar chamada duplicada de `iniciar_sessao` no executor SDK.
- Definir erros de domínio e rate limit no contrato A2A.
- Consolidar arquivos A2A duplicados depois de escolher entre o contrato manual e o SDK.

## Arquivos

`src/frigus_ai/a2a/`, `src/frigus_ai/api/app.py`, `src/frigus_ai/api/auth.py`,
`tests/api/test_a2a.py`.
