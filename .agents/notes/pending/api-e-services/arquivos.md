# Migração API e Services

## Feito

- `ChatService` foi introduzido como ponto de entrada das interfaces.
- Foram adicionados criação, listagem e ownership de chats.
- Middleware de segurança não inicializa Redis no modo demo.
- Rotas diretas de domínio (`routes/stock.py`, `routes/shopping.py`, `routes/recipes.py`):
  CRUD de estoque, lista de compras e leitura de receitas, chamando a mesma camada de
  `repositories/` que as tools do LLM usam. Rate limit por rota com `@guard.rate_limit(...)`
  (`SecurityDecorator` do `fastapi-guard`, já dependência do projeto — sem adicionar `slowapi`)
  nas rotas de escrita. Exceções de estoque/compras (`ItemDeEstoqueNaoEncontrado`,
  `QuantidadeNegativa`, `ItemDeCompraNaoEncontrado`, `ProdutoNaoCadastrado`,
  `EstoqueAtualNaoDefinido`) mapeadas em `exception_handler.py`.

## Falta fazer

- Remover a duplicação entre funções de módulo e métodos de `ChatService`.
- Tirar bootstrap de usuário/estoque de `chat/service.py`.
- Criar schemas para todas as respostas da API.
- Versionamento (`/v1`) e CSRF ainda não existem — nenhuma rota tem prefixo de versão hoje
  (`/chats`, `/keys`, e agora `/stock`, `/shopping-list`, `/recipes`), então adicionar `/v1` só
  nas rotas novas criaria inconsistência; é mudança pra todas as rotas de uma vez.
- Validar ownership em todas as rotas.
- Consolidar a rota A2A antiga com a implementação SDK.
- `/v1/profile` (perfil alimentar) e `/v1/stock/foto` (visão) ficam pra quando as fases 2 e 4
  do plano (`PENDENCIAS.md`) forem implementadas — as rotas de estoque/compras/receitas de hoje
  cobrem só a fase 1 (CRUD direto + rate limit + exceções tipadas).

## Arquivos

`src/frigus_ai/api/`, `src/frigus_ai/services/chat/`, `src/frigus_ai/schemas/`.
