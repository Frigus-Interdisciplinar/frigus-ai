# Gaps restantes: Frigus.AI x assessor-ai

> **Nota obsoleta — arquivada em 2026-09-23.** Descrevia gaps contra uma integração A2A via
> `a2a-sdk` (`src/frigus_ai/a2a/`), removida do repo — decisão registrada em `AGENTS.md`
> ("Estrutura"), ver também `implemented/a2a-sdk/arquivos.md`. Também referencia
> `services/chat/service.py` (pacote) e `services/types.py`, que hoje são o módulo flat
> `services/chat_service.py` e `frigus_ai/types.py`. A migração `ToolSet`→`*Repo` descrita na
> seção "Tools/repositories" terminou (ver `implemented/tools-repos/arquivos.md`). Nada aqui
> reflete o código atual — fonte de verdade agora é
> `pending/requisitos-disciplina/arquivos.md`. Conteúdo original abaixo só como histórico.

Esta nota é o mapa de trabalho principal para a próxima sessão.

## Gaps críticos

### A2A

- O SDK foi instalado e montado, mas os testes antigos ainda usam `message/send`, enquanto o SDK
  atual trabalha com `SendMessage` e o formato protobuf/JSON correspondente.
- O Agent Card do SDK serializa `supportedInterfaces`; não assumir o formato manual anterior com
  `protocolVersion` e `url` na raiz.
- O executor atual ainda usa `DEMO_USER_ID`.
- O executor SDK ainda chama `iniciar_sessao` novamente depois de resolver a sessão; evitar duplicação.
- A autenticação A2A via `X-API-Key` ainda não foi ligada ao `ServerCallContext`.
- Definir tratamento de erro de rate limit e erros de domínio no protocolo SDK.

Arquivos principais:

- `src/frigus_ai/a2a/main.py`
- `src/frigus_ai/a2a/card.py`
- `src/frigus_ai/a2a/interface.py`
- `src/frigus_ai/api/auth.py`
- `src/frigus_ai/api/app.py`
- `tests/api/test_a2a.py`
- referência: `assessor-ai/src/assessor_ai/a2a/`

### API

- A API ainda não está no mesmo nível do assessor em versionamento, limiter, CSRF, schemas,
  handlers e endpoints de usuário/perfil.
- `GET /chats` foi iniciado, mas retorna `list[dict]` e precisa de schema.
- Ownership precisa ser aplicado consistentemente em todas as rotas.
- A rota A2A manual e a integração SDK ainda coexistem; escolher um contrato e consolidar/remover
  o outro com testes.
- O middleware de segurança foi condicionado à flag para o modo demo; revisar se o comportamento
  de produção está coberto por testes.

Arquivos principais:

- `src/frigus_ai/api/app.py`
- `src/frigus_ai/api/routes/chats.py`
- `src/frigus_ai/api/routes/a2a.py`
- `src/frigus_ai/api/auth.py`
- `src/frigus_ai/api/middleware.py`
- `src/frigus_ai/api/exception_handler.py`
- `src/frigus_ai/schemas/`
- referência: `assessor-ai/src/assessor_ai/api/`

### Services

- `ChatService` existe, mas a lógica continua duplicada entre funções de módulo e métodos da
  classe.
- Bootstrap de usuário/estoque está dentro de `chat/service.py`, misturando caso de uso,
  persistência e infraestrutura.
- `services/types.py` é uma fachada temporária; a fonte correta agora é `frigus_ai/types.py`.
- `services/chat/repositories.py` ainda funciona como fachada de funções para vários módulos,
  não como repository de domínio no mesmo nível do assessor.

Arquivos principais:

- `src/frigus_ai/services/chat/service.py`
- `src/frigus_ai/services/chat/repositories.py`
- `src/frigus_ai/services/chat/mongo.py`
- `src/frigus_ai/services/types.py`
- referência: `assessor-ai/src/assessor_ai/services/` e `repositories/`

### Tools/repositories

- Os nomes principais foram corrigidos para `repo.py`/`*Repo`, mas `toolset.py` continua como
  compatibilidade.
- `ToolSet` ainda é a classe-base; decidir se deve ser renomeada/removida depois de consolidar
  todos os imports, sem apagar sem autorização.
- Os domínios Postgres ainda usam SQL cru e não seguem o `PostgresRepo`/`@transacional` do
  assessor.
- Ainda falta avaliar se os models SQLAlchemy em `infra/postgres/models/` cobrem todos os domínios.
- Faq e Spoonacular têm fachadas de teste que precisam ser substituídas por testes contra `repo.py`
  quando a migração estabilizar.

Arquivos principais:

- `src/frigus_ai/graph/tools/*/repo.py`
- `src/frigus_ai/graph/tools/*/toolset.py`
- `src/frigus_ai/graph/tools/__init__.py`
- `src/frigus_ai/infra/postgres/`
- referência: `assessor-ai/src/assessor_ai/graph/tools/`

### Infra

- Classes lazy foram adicionadas, mas o padrão ainda não está completo.
- Falta decidir e implementar `MongoRepo` genérico.
- Falta revisar dispose/close e o lifespan de todas as conexões.
- Health check agora testa cada dependência separadamente; falta validar o resultado com a stack real.
- Confirmar a separação entre pool síncrono das tools e pool async do checkpointer.

Arquivos principais:

- `src/frigus_ai/infra/base.py`
- `src/frigus_ai/infra/postgres/connection.py`
- `src/frigus_ai/infra/mongo/connection.py`
- `src/frigus_ai/infra/redis/connection.py`
- `src/frigus_ai/infra/qdrant/connection.py`
- `src/frigus_ai/api/lifespan.py`
- `src/frigus_ai/api/routes/health.py`
- referência: `assessor-ai/src/assessor_ai/infra/`

## Critério de conclusão

Considerar o alinhamento concluído somente quando:

- A2A SDK funcionar com testes próprios do contrato atual.
- API, A2A e TUI passarem pelo mesmo service/repository sem duplicar regras.
- Cada domínio de tool tiver `repo.py`, schema e testes coerentes.
- Conexões forem lazy e o ciclo de vida estiver explícito.
- Não houver imports de `toolset` fora das fachadas temporárias.
- `ruff`, compilação e a suíte completa passarem.
