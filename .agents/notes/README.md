# Handoff: refactor Frigus.AI alinhado ao assessor-ai

## Como continuar em outra sessão

1. Ler este arquivo inteiro antes de alterar qualquer coisa.
2. Ler `AGENTS.md` e respeitar a regra: **não alterar nem apagar código sem solicitação explícita**.
3. Ler primeiro as notas pendentes em `pending/`, especialmente:
   - `pending/requisitos-disciplina/arquivos.md` — **começa por aqui**: placar dos requisitos
     e ordem P0/P1/P2 do que ainda falta pra nota
   - `pending/a2a-sdk/arquivos.md`
   - `pending/api-e-services/arquivos.md`
   - `pending/tools-repos/arquivos.md`
   - `pending/guardrail-privacy/arquivos.md`
   - `pending/gap-assessor/arquivos.md`
4. Consultar `implemented/` para entender o que já foi feito:
   - `implemented/contratos-grafo-e-repositories/arquivos.md` — sessão mais recente
   - `implemented/infra-conexoes/arquivos.md`
   - `implemented/tipos-compartilhados/arquivos.md`
5. Usar o assessor local como referência:
   `C:\Users\davifranco-ieg\OneDrive - Instituto J&F\Área de Trabalho\Codes\IA\assessor-ai`.
6. Conferir `git status --short --branch` antes de editar. O worktree já estava muito sujo
   antes desta migração; não reverter alterações preexistentes.

## Estado da sessão anterior

Branch atual: `refactor/structure`. Suíte: **177 passed**, ruff limpo.

Detalhe completo em `implemented/contratos-grafo-e-repositories/arquivos.md`. Resumo:

- `graph/builder.py` estava com **erro de sintaxe** (não importava) — reescrito no padrão que
  estava comentado embaixo dele, com `input_schema`/`output_schema`.
- Grafo ganhou contratos tipados: `AsyncNode[R]`, `EntradaGrafo`/`SaidaGrafo` e um `*Update`
  por nó. Nós usam classes de mensagem, não `{"role": ...}`.
- `graph/names.py` saiu de `nodes/` pra quebrar ciclo de import real (o assessor tem o mesmo
  ciclo latente).
- `graph/nodes/contexto.py`: `responder`, `perguntar`, `mensagens_do_turno`, `podar_historico`.
- Histórico do grafo agora tem teto (`MAX_MENSAGENS = 21`) — antes crescia sem limite e todo
  turno relia tudo pro LLM.
- `financeiro` e `estoque` migrados pra SQLAlchemy + `@transacional`. Sobrou `compras`.
- `frigus_ai/privacy.py` criado; `guardrail/` saiu de `nodes/` pra `graph/guardrail/`.
- Três correções: ownership faltando no `/stream`, Redis sem timeout (~4s por chamada com o
  serviço fora do ar) e `Categoria(...)` estourando em categoria desconhecida.
- `TODO.md` foi apagado (era legado) e as referências a ele, limpas.

### Não repetir

- Não reintroduzir `{"role": ...}` nos nós; usar `HumanMessage`/`AIMessage`/`SystemMessage`.
- Não voltar `names.py` nem PII pra dentro de `nodes/` — os dois saíram por causa de ciclo de
  import e de inversão de dependência reais, não por estética.
- Não checar ownership no corpo de rota que é gerador (SSE): tem que ser dependência, senão
  roda depois que o status HTTP já saiu.

## Ordem recomendada para a próxima sessão

### P0 — fazer o app e os contratos ficarem coerentes

1. Corrigir o A2A com o contrato real do SDK:
   - usar `SendMessage`, não depender apenas do JSON-RPC manual antigo;
   - confirmar o formato de `AgentCard` (`supportedInterfaces`, sem assumir `protocolVersion`
     no nível raiz);
   - fazer o executor usar o service correto e não chamar `iniciar_sessao` duas vezes;
   - propagar autenticação para o contexto A2A, em vez de usar sempre `DEMO_USER_ID`;
   - definir como `X-API-Key` chega ao `ServerCallContext`;
   - adicionar testes compatíveis com o SDK e preservar o comportamento de sessão por
     `context_id`;
   - decidir explicitamente se erros de rate limit A2A são transporte HTTP ou mensagem A2A.

2. Corrigir a API de chat:
   - `POST /chats` deve criar o chat persistido e devolver apenas o contrato decidido;
   - `GET /chats` deve ter schema de resposta, não `list[dict]`;
   - todas as rotas de chat devem validar ownership antes de acessar histórico ou enviar mensagem;
   - alinhar prefixo/versionamento com o assessor (`/v1/chats`) somente se isso for uma decisão
     do projeto, atualizando clientes e testes juntos;
   - revisar `create_chat`, `send_message`, streaming, histórico e fechamento em conjunto;
   - não deixar a rota A2A manual antiga competir com as rotas registradas pelo SDK.

3. Fazer `services/chat/service.py` ser a camada de caso de uso real:
   - manter uma classe com dependências claras;
   - mover lógica de bootstrap de usuário/estoque para um repository ou service apropriado;
   - retirar gradualmente as funções de módulo e fachadas temporárias;
   - não criar `service_v2.py` nem outro arquivo paralelo;
   - atualizar todos os chamadores e testes.

### P1 — terminar o padrão de repositories das tools

1. Para cada domínio (`estoque`, `compras`, `receitas`, `financeiro`, `faq`, `spoonacular`):
   - manter `schemas.py`, `repo.py` e, quando necessário, `models.py`;
   - o repository deve encapsular o estado/conexão necessário;
   - expor tools por `as_tools()` com `StructuredTool.from_function` em bound methods;
   - não usar `@tool` em métodos de classe;
   - usar `Response` em todos os caminhos de sucesso/erro;
   - preservar escopo por `session_context`; nunca adicionar `user_id`/`stock_id` ao schema enviado
     pelo LLM.

2. Migrar os domínios Postgres do SQL cru para o padrão do assessor somente após ler:
   - `data/sql/schema.sql`;
   - schemas e testes de cada domínio;
   - `infra/postgres/connection.py`;
   - os models SQLAlchemy já existentes em `infra/postgres/models/`.

3. Criar/ajustar `PostgresRepo` e transação compartilhada se isso realmente couber no schema atual.
   Não copiar cegamente os models do assessor: os IDs e tabelas do Frigus são diferentes.

4. Manter `toolset.py` apenas enquanto houver testes/imports dependentes. A remoção física exige
   autorização prévia do usuário. Quando houver autorização, consolidar os imports e apagar as
   fachadas em uma mudança separada.

### P1 — completar infra e ciclo de vida

- Revisar `MongoConn` para expor `MongoRepo` genérico como no assessor, se os repositories Mongo
  forem realmente migrados para classes.
- Revisar dispose/close de Postgres, Mongo, Redis, Qdrant e Spoonacular no lifespan.
- Garantir que nenhuma conexão faça I/O no import.
- Conferir se o checkpointer do LangGraph usa a conexão e pool corretos após o refactor.
- Não misturar o pool psycopg2 síncrono das tools com o pool async do checkpointer sem documentar.
- Adicionar health checks isolados por dependência, sem um `try` único que esconda qual serviço
  falhou.

### P2 — qualidade, testes e documentação

- Atualizar testes A2A para o SDK real.
- Atualizar testes de API para os novos schemas e ownership.
- Adicionar testes de repositories por domínio com fronteira de banco mockada.
- Rodar `just check` e `just test` completos antes de concluir.
- Atualizar README/estrutura quando a organização final estiver decidida.
- Manter notas em `.agents/notes/`. O `TODO.md` não existe mais — não recriar.

## Restrições importantes

- Não apagar arquivos sem permissão prévia.
- Não restaurar ou reverter os arquivos marcados como deletados no `git status`: muitos fazem parte
  de uma migração estrutural preexistente feita pelo usuário.
- Não commitar `.env` nem expor credenciais.
- Não usar os arquivos `toolset.py` como arquitetura principal; eles são compatibilidade.
- Não declarar que A2A está pronto só porque o Agent Card responde 200.
- Não considerar testes antigos passando como prova de compatibilidade do SDK: eles ainda exercitam
  o protocolo manual legado.
