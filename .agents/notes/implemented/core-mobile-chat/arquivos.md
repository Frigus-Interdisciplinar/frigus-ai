# Chat mobile pelo Core

## Fluxo

O app continua usando `POST /mobile/recipes/ai/chat` no BFF. O Core autentica o usuário
e chama `POST /internal/core/chat` na IA, com `userId`, `stockId`, `message`,
`sessionId?` e `foodPreferences`. Essa rota exige `X-Core-Service-Key`, mesmo quando
a autenticação pública da IA está desligada para desenvolvimento.

`API_KEYS__CORE_SERVICE_KEY` na IA e `FRIGUS_AI_API_KEY` no Core devem conter o mesmo
segredo aleatório de pelo menos 32 caracteres, exclusivamente nos servidores.
`FRIGUS_AI_BASE_URL` é a origem da IA, sem `/v1`. Os dois serviços devem usar o mesmo
Postgres: a IA confirma o vínculo ativo usuário/grupo/estoque e o dono da conversa.
Não há chave compartilhada identificando todos os usuários como uma única conta.

## Receitas

O contexto `domain/recipe_turn.py` é limitado a uma requisição e chega às tools via
ContextVar. `match_recipes_to_stock` retorna candidatos do estoque pedido, com saldo
positivo e validade vigente. Na integração Core não grava candidatos automaticamente.
Preferências estruturadas retiram ingredientes incompatíveis conhecidos antes do ranking;
as preferências atuais também entram no prompt. Alergias do perfil continuam relevantes.
Os filtros por nome/categoria não certificam ausência de alérgenos ou contaminação cruzada.

A tool `salvar_sugestoes_receitas` registra somente IDs consultados naquele turno,
escolhidos pelo especialista depois de considerar as preferências e a conversa.
A resposta interna devolve esses IDs. O Core confirma as receitas no catálogo e grava
ou atualiza `recipe_suggestions`; somente então responde ao mobile. Não se associa
receita antiga por coincidência no texto. Conversas sem recomendações devolvem lista vazia.
Nesta integração as recomendações salvas usam receitas do catálogo compartilhado;
o especialista é instruído a não recomendar alternativas externas que não possam ser salvas.

## Arquivos

- `schemas/core_chat.py`, `api/routes/core_chat.py`, `services/core_chat_service.py`:
  contrato privado, credencial de serviço e orquestração.
- `repositories/identidade_repository.py`: autorização explícita do estoque pedido.
- `domain/recipe_turn.py`, `graph/agents.py`, `graph/prompts/receitas.md`,
  `graph/tools/receitas/{repo,schemas}.py`: preferências atuais e seleção explícita de IDs.
- `repositories/receitas_repository.py`: exclusões alimentares e estoque utilizável.
- `settings/api_keys.py`, `.env.example`: configuração do segredo.
- `domain/errors.py`: erro de acesso ao estoque, traduzido pelo handler existente.
- `tests/api/test_core_chat.py`, `tests/repositories/test_receitas_core.py`: contrato,
  autorização, propagação do contexto e consultas SQL reais em banco de teste em memória.

O `.env` local foi migrado dos nomes antigos para o formato aninhado do Settings,
preservando valores e alinhando a chave de serviço ao Core. Nenhuma credencial foi versionada.

## Validação

`python -m pytest -q`: 462 testes passaram. Ruff nos arquivos alterados passou.
A configuração real carrega, a rota interna aparece no OpenAPI e as configurações
locais de Core/IA compartilham banco e chave de serviço. Não foi feita uma conversa
com o provedor real no aparelho nesta validação.

Uma chamada curta ao `llm_especialista`, com configuração local real e tracing
desativado apenas no processo de teste, recebeu resposta do provedor. Não executou
tools nem criou conversa/dados no banco. Os 17 testes afetados passaram novamente
após acrescentar a cobertura que impede sucesso fictício fora do contexto Core.
