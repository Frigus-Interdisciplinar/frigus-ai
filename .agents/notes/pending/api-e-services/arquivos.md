# Migração API e Services

## Feito

- `ChatService` foi introduzido como ponto de entrada das interfaces.
- Foram adicionados criação, listagem e ownership de chats.
- Middleware de segurança não inicializa Redis no modo demo.

## Falta fazer

- Remover a duplicação entre funções de módulo e métodos de `ChatService`.
- Tirar bootstrap de usuário/estoque de `chat/service.py`.
- Criar schemas para todas as respostas da API.
- Alinhar versionamento, limiter, CSRF, handlers e endpoints com o assessor.
- Validar ownership em todas as rotas.
- Consolidar a rota A2A antiga com a implementação SDK.

## Arquivos

`src/frigus_ai/api/`, `src/frigus_ai/services/chat/`, `src/frigus_ai/schemas/`.
