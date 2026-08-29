# TODO

Próximos passos planejados. Contexto do projeto e checklist de requisitos da disciplina em
[AGENTS.md](AGENTS.md).

## CONTEXTO_TEMPORAL congelava na data do import — corrigido

Bug pré-existente (não era regressão do refactor de prompts pra `.md`, foi preservado por fidelidade
na conversão): `loader.py` computava a data uma vez no import, e `graph/agents.py` embutia o
resultado dentro de `create_agent(system_prompt=...)` também no import. Num processo de vida longa
(API rodando, TUI aberta na virada do dia), o agente respondia com a data de quando o processo
subiu — errado justamente em "o que vence hoje", que é o core do domínio.

- [x] **`contexto_temporal()` virou função**, chamada por `load_prompt()` a cada chamada. O que
      passou a ser cacheado (`lru_cache`) é o parse do `.md`, que não muda em runtime — não o prompt
      pronto.
- [x] **Os 7 agentes de `graph/agents.py` recebem o prompt por `dynamic_prompt`** (middleware do
      LangChain) em vez de `system_prompt=`, então o prompt é remontado a cada chamada de modelo.
      Ficou mais curto que antes: os 7 `create_agent` repetidos viraram um helper `_montar()`.
      **Não** foi preciso mexer em mensagem de sistema por turno como o skill sugeria — logo a
      ressalva de providers do `.agents/skills/langchain.md` (Gemini fundindo system messages
      extras) não se aplica, porque continua havendo exatamente uma system message.
- [x] **Juiz/Resumidor/Perfil também congelavam** (montavam o prompt em constante de módulo) —
      `agents/nodes/juiz.py` e `tools/mongo/helpers.py` agora chamam `load_prompt()` dentro da
      função.
- [x] Regressão coberta por `tests/agents/prompts/test_loader.py`.

## Refatoração de estrutura — alinhar com o assessor-ai — concluída

`main.py` hoje mistura três coisas: o loop de terminal, a lógica de montar/persistir mensagens e a
invocação do grafo (`executar_fluxo_frigus`, `_extrair_resposta`, `salvar_mensagens`). Isso trava a
criação de uma API sem duplicar essa lógica — exatamente o problema que o projeto irmão
**assessor-ai** (`Codes/IA/assessor-ai`) já resolveu. Ele é a estrutura de referência para este
refactor (ainda sem MCP/A2A implementados lá também, mas o resto — camada de serviço, tests, CI,
observabilidade — está mais maduro que aqui).

Também vira **pacote `src/`**, igual assessor-ai: toda a lógica agentica (`agents/`, `graph/`,
`tools/`, e o novo módulo de serviço abaixo) migra para dentro de `src/frigus_ai/` (nome do pacote
com underscore, já que `pyproject.toml` usa `name = "frigus-ai"` com hífen — mesma convenção do
assessor-ai: `name = "assessor-ai"` → pacote `src/assessor_ai`). `config/` e as interfaces
(`ui/` → `interfaces/`) continuam soltos no root, fora de `src/` — só o "cérebro" entra no pacote.

Estrutura alvo (nome exato do módulo de serviço é o de menor prioridade — decidir na hora, seguindo
o motivo documentado no TODO do assessor-ai: evitar colidir com `graph/` já sendo o "flow" do
LangGraph e `agents/` já sendo "agent"):

```text
src/frigus_ai/
├── agents/             # o que hoje é agents/ no root
├── graph/              # o que hoje é graph/ no root
├── tools/              # o que hoje é tools/ no root
└── chat/ (ou nome equivalente)
    ├── models.py          # contrato de mensagem interno, independente do schema do Mongo
    ├── repositories.py    # acesso a tools/mongo/{chats,users} e tools/postgres/*
    ├── runner.py          # invoca fluxo_agentes.invoke (graph/builder.py), extrai a resposta
    └── service.py          # create_chat(), send_message(), get_history(), encerrar_sessao()

interfaces/terminal/    # ui/ migra pra cá, fora de src/
├── app.py              # loop de input() do terminal, usando chat.service
└── display.py          # o que hoje é ui/terminal.py

config/                 # continua no root, fora de src/ (mesmo lugar do assessor-ai)
```

- [x] Criar `src/frigus_ai/` e mover `agents/`, `graph/`, `tools/` pra dentro (`git mv` + sed nos
      imports `agents.`/`graph.`/`tools.` → `frigus_ai.agents.`/etc., incluindo a string
      `LANGGRAPH_ALLOWED_MSGPACK_MODULES` em `graph/builder.py`, que também referenciava esses
      caminhos). Pacote instalável via `hatchling` — `pyproject.toml` **não tinha `[build-system]`
      nenhum** (achado: só existia `[tool.setuptools.packages.find]`, sem cobrir `main.py`/`api`/
      `mcp_server`/`a2a_server`) — adicionado `[build-system]` + `[tool.hatch.build.targets.wheel]
      packages = ["config", "interfaces", "src/frigus_ai"]`, mesmo bloco do assessor-ai. Verificado:
      `uv sync` builda o pacote com sucesso
- [x] Extraído pra `src/frigus_ai/chat/`: `models.py` (`ChatMessage`/`Role`, contrato próprio,
      convertido de/para `tools.mongo.chats.schemas.Mensagem` em `repositories.py`),
      `repositories.py` (wrappers sobre `tools/mongo/{chats,users}/core.py`), `runner.py`
      (`executar_fluxo_frigus` + `_extrair_resposta` de `main.py`), `service.py` (`send_message`,
      `get_history`, `encerrar_sessao`, `iniciar_sessao` — bootstrap do usuário demo movido de
      `main.py` pra cá, pra não violar a regra de interface não tocar `tools.postgres.*` direto).
      **Simplificação deliberada:** sem `create_chat()` — nada usa hoje (o terminal cria o doc do
      chat de forma preguiçosa dentro de `salvar_mensagens`, igual já fazia o `main.py` antigo);
      adicionar quando a API precisar de um chat pré-criado pra checar ownership antes da primeira
      mensagem (mesmo motivo que levou o assessor-ai a criar essa função)
- [x] `main.py` virou dispatcher fino (`python main.py <interface>`, hoje só resolve `terminal`)
- [x] `ui/terminal.py` migrou pra `interfaces/terminal/display.py` sem mudança de conteúdo;
      `interfaces/terminal/app.py` (novo) é o loop de `input()`, usando só `chat.service`
- [x] Nenhuma interface chama `frigus_ai.graph.builder`/`frigus_ai.tools.*` direto — só
      `frigus_ai.chat.service`

**Verificado:** `uv sync` builda o pacote sem erro; smoke test de import (`frigus_ai.chat.service`,
`frigus_ai.graph.builder`, `main`) com env vars dummy resolve a cadeia inteira (agents/prompts/
tools/graph, todos os 10 nós) sem `ModuleNotFoundError`. **Não verificado nesta sessão:** rodar
`python main.py terminal` ponta a ponta contra Postgres/Mongo reais — não havia `.env` nem Docker
disponíveis neste ambiente. Rodar localmente antes de dar merge.

## Env vars — estado atual e gestão remota (Infisical)

`.env.example` bate 1:1 com `config/settings.py:Settings` hoje (`GEMINI_API_KEY`, `GROQ_API_KEY`,
`ANTHROPIC_API_KEY`, `POSTGRES_URI`, `MONGODB_URI`, `LANGSMITH_TRACING`/`LANGSMITH_API_KEY`/
`LANGSMITH_PROJECT`) — nenhum campo faltando. O que falta é o env **final**, que só fica completo
conforme as features pendentes entrarem. Já documentado como comentário no `.env.example` pra não
virar surpresa:

- [ ] `REDIS_URL` — entra com a primeira tool de Redis
- [ ] `QDRANT_URL` / `QDRANT_API_KEY` / `QDRANT_COLLECTION_NAME` — entram com a migração do FAQ
- [ ] Se a API sair deste repo, o que ela precisar de auth (ex.: um secret de signup, como o
      `SIGNUP_SECRET` do assessor-ai)

**Regra:** não adicionar campo ao `Settings` antes da feature existir. `Settings()` é instanciado no
import de `config/settings.py`, então campo obrigatório sem uso quebra o projeto inteiro pra quem
não tiver a var — foi exatamente o que obrigou o `tests/conftest.py` a existir.

### Infisical para env remota — viável, mesmo caminho do assessor-ai

O assessor-ai já usa (`.infisical.json` + `just dev` = `infisical run -- <cmd>`), então é caminho
testado no projeto irmão, não aposta. O mecanismo é simples: o CLI busca os segredos do workspace e
injeta no ambiente do processo filho — o código não muda nada (continua lendo via `pydantic-settings`),
e `.env` local segue funcionando pra quem não quiser usar.

Vantagem concreta pro trabalho em grupo: hoje cada pessoa mantém o próprio `.env` na mão, e chave
nova (as pendentes acima) vira mensagem no grupo. Com Infisical, é um `infisical run` e todo mundo
tem a mesma versão.

- [ ] Confirmar que o tier gratuito cobre o tamanho do time e os ambientes necessários — **verificar
      antes de adotar**, não assumir (mesma cautela da seção de Observabilidade: a escola não paga
      ferramenta)
- [ ] Criar o workspace, subir os segredos e commitar `.infisical.json` (só tem `workspaceId` e
      mapeamento de ambiente — não carrega segredo nenhum, pode ir pro repo)
- [ ] Adicionar a receita `dev` ao `justfile` (`infisical run -- {{cmd}} {{mode}}`), mantendo `run`
      como está pra quem usa `.env` local
- [ ] Documentar no README qual dos dois caminhos usar

**Não bloqueia nada.** O `.env` local resolve hoje; isso é conveniência de time e higiene de segredo
(evita chave circulando por chat/pendrive), não pré-requisito de nenhuma feature.

## Interfaces — terminal removido, TUI é a única interativa

`interfaces/terminal/` (o loop de `input()` original) foi removido — a TUI (Textual, portada do
assessor-ai) cobre o mesmo caso de uso com uma experiência melhor, não fazia sentido manter as duas.
`main.py` resolve `tui` (default) e `api` hoje (`python main.py <interface>`); `justfile`'s `run`
já aponta pra `tui` por padrão.

- [ ] Se algum dia fizer falta um modo texto puro sem Textual (ex. rodar em CI/scripting), reavaliar
      — não recriar só por precaução, sem caso de uso concreto ainda

## Seleção interativa de interface (questionary) — avaliado, ainda adiado

`main.py` resolve `tui` e `api` hoje — 2 modos, decorar o nome ainda é barato o suficiente pra não
justificar a dependência nova. Reavaliar se um terceiro modo (frontend, MCP como modo próprio) aparecer.

- [ ] Adicionar `questionary` como dependência quando compensar (2 opções ainda é pouco atrito).
      Desenho: `python main.py <interface>` continua funcionando direto (scriptável, usado por
      CI/automação); `python main.py` sem argumento cai no menu interativo do `questionary` como
      atalho amigável — as duas formas convivem, não é substituição

## API (FastAPI/Flask) — requisito da disciplina

**Localização decidida: mesmo repositório** (ver "Decisão: API no mesmo repo ou separado?" abaixo).

Seguir o padrão do assessor-ai (`interfaces/api/`): `main.py` (app FastAPI), `auth.py` (se precisar
de API key), `routes/` por recurso (`chats`, `health`), `schemas/` (Pydantic de request/response).
Rotas chamam só o módulo de serviço, nunca o grafo ou as tools direto. Ver
`.agents/skills/fastapi.md` antes de mexer em `interfaces/api/`.

- [x] **Esqueleto de rotas**: `interfaces/api/{main,routes/{chats,health},schemas/{chat,health}}.py`
      — `POST /chats`, `POST /chats/{id}/messages`, `GET /chats/{id}/messages`, `GET /health/{live,ready}`
      (`/ready` checa Postgres/Mongo/Redis/Qdrant, 503 se algum estiver fora). Sem `auth.py`
      nem rate limiting — não fazia sentido copiar isso do assessor-ai ainda (nenhum dos dois itens
      abaixo está resolvido, então não tem o que autenticar/limitar por usuário de verdade).
      **Simplificação deliberada, precisa de retrabalho quando os itens abaixo saírem:** `user_id`
      hardcoded em `DEMO_USER_ID` em cada rota (mesmo bootstrap do terminal/TUI) e `stock_id`
      reresolvido via `iniciar_sessao()` a cada request (idempotente, mas ineficiente sem sessão
      persistente)
- [ ] Controle de sessão por usuário de verdade (hoje é só `thread_id` gerado em memória na TUI) —
      ver item "Checkpointer persistente" abaixo, é pré-requisito. Depois disso, trocar `DEMO_USER_ID`
      hardcoded nas rotas por auth de verdade
- [x] **Tratamento de erro nas rotas** — `LimiteDeMensagensExcedido` agora vira **429 +
      `Retry-After: 60`**, e o `except Exception` genérico virou `logger.exception(...)` + `detail`
      fixo (antes devolvia `str(e)`, vazando mensagem crua do psycopg2/pymongo pro cliente).
      Registrado como pegadinha em `.agents/skills/fastapi.md`
- [x] **`DELETE /chats/{chat_id}`** — 202 Accepted + `BackgroundTasks`, que agenda
      `chat_service.encerrar_sessao` (resumo + perfil, duas chamadas de LLM) fora do caminho da
      resposta. **Zero infra nova** — ver decisão na seção "Redis e Qdrant" sobre não subir fila
      ainda. Destrava "memória de longo prazo" pelo caminho HTTP, que antes nunca gerava perfil
- [x] **BUG pré-existente: a API não subia.** `schemas/chat.py` montava `_ROLE_MAP` acima da
      declaração do `class Role` local, com o `Role` do domínio ainda shadowando o nome —
      `AttributeError` no import, `uvicorn interfaces.api.main:app` não iniciava. Não havia teste
      que importasse `interfaces.api.main`; agora há
- [x] **Primeiro teste de API do repo** — `tests/interfaces/api/test_chats.py`, `TestClient` com
      `chat_service` mockado (sem Postgres/Mongo/Redis): 429 com header, 500 sem vazar texto
      interno, happy path e o 202 do DELETE
- [ ] Rate limiting básico por IP (o por usuário já existe via Redis). **Nota:**
      falta só o limite por IP; o por usuário (`tools/redis/chat.py`, 10 msg/60s) já roda e agora
      responde o status HTTP certo

## Checkpointer persistente (controle de sessão) — concluído

`graph/builder.py` usava `MemorySaver` — estado do LangGraph sumia a cada restart do processo. Agora
usa `MongoDBSaver`, então a sessão sobrevive a restart/redeploy (requisito "controle de sessões por
usuário" da disciplina).

- [x] `MongoDBSaver` (`langgraph-checkpoint-mongodb>=0.4`) — reusa o Mongo que o projeto já tem, sem
      infra nova. Coleções nomeadas à parte (`graph_checkpoints`/`graph_checkpoint_writes`) pra não
      colidir com os defaults da lib nem com `agent_chats`/`user_profiles`. Recebe o `MongoClient` via
      `banco.client` (`tools/mongo/connection.py`), sem abrir conexão nova nem mexer nesse módulo.
      **Achado 1 (o mesmo do assessor-ai, confirmado aqui):** a lib trava `pymongo<4.17` e o projeto
      pinava `pymongo>=4.17` — relaxado pra `>=4.12,<4.17` (instalou 4.16.0). **Achado 2:** o `uv`
      também exigiu `requires-python = ">=3.13,<3.14"` (antes era só `>=3.13`) — sem o teto, a
      resolução falha pro split de Python 3.14, onde não existe versão compatível da lib. **Achado 3:**
      o módulo importável é `langgraph.checkpoint.mongodb` (namespace do langgraph), não
      `langgraph_checkpoint_mongodb` (nome do dist)
- [x] `fluxo_agentes` deixou de ser variável de módulo (compilava o grafo no import) e virou função
      com `@functools.cache` — necessário porque o `MongoDBSaver` toca o Mongo, e a convenção do
      projeto é nenhuma conexão no import. Call site (`chat/runner.py`) virou `fluxo_agentes().invoke(...)`
- [ ] Confirmar que `thread_id` (hoje `session_id` gerado por `uuid4()` em `interfaces/tui/app.py`)
      continua sendo a chave certa quando existir usuário autenticado de verdade (via API)

**Verificado:** o grafo compila com o `MongoDBSaver` apontando pro db `frigus_ai` e as coleções
certas, e o `functools.cache` devolve a mesma instância entre chamadas. **Não verificado nesta
sessão:** gravar/recuperar estado contra um Mongo real (Docker não estava rodando no ambiente) —
rodar `python main.py tui`, matar o processo e reabrir com o mesmo `session_id` pra confirmar
que o estado do grafo sobrevive, antes de dar merge.

## MCP e A2A

Requisito explícito da disciplina. `mcp_server/`, `a2a_server/` e `api/` foram **removidos do repo**
(eram só `__init__.py` vazio, sem implementação nenhuma — recriar quando o trabalho de cada um
começar de verdade, não versionar pasta placeholder sem uso).

- [ ] **MCP**: expor as tools do Frigus.AI (estoque, compras, receitas, financeiro, faq) como
      servidor MCP, pra hosts MCP externos (Claude Desktop etc.) conseguirem consumir o domínio do
      Frigus sem precisar do grafo inteiro. Quando `tools/spoonacular/core.py` existir (ver seção
      "Spoonacular" abaixo), entra na mesma lista — é só mais um domínio de consulta, mesmo padrão
      das demais
- [ ] **A2A**: expor `fluxo_agentes` (ou o módulo de serviço, pós-refactor) como agente
      Agent-to-Agent, pra outro sistema multiagente conseguir conversar com o Frigus.AI como um
      agente externo
- [ ] Decidir se os dois vivem só neste repo ou se algum consome a API (API fica neste repo —
      decidido, ver seção "API (FastAPI/Flask)" acima)
- [ ] **Em discussão:** usar o A2A como *cliente* também, não só servidor — trocar o agente
      `financeiro` local por uma chamada A2A pro domínio financeiro do assessor-ai, já que os dois
      projetos são irmãos. **Ressalva a resolver antes de decidir:** o `financeiro` do Frigus
      (`tools/postgres/financeiro/core.py`, `MesArgs`/`EvolucaoDesperdicioArgs`) parece ser sobre
      gasto/desperdício de alimentos cruzado com o estoque, não finanças pessoais genéricas — é um
      domínio diferente do `financeiro` do assessor-ai (transações/eventos genéricos, schema Postgres
      separado, `user_id` desacoplado do Frigus). Antes de substituir, confirmar se faz sentido
      semântico (não só técnico) chamar um agente externo pra um dado que hoje é local e correlacionado
      com `estoque`/`compras`. Se o objetivo é só ter uma demonstração real de A2A como cliente (além
      de servidor), talvez `agenda`/calendário do assessor-ai seja um alvo melhor que `financeiro`, por
      não sobrepor um domínio que o Frigus já possui nativamente

## Observabilidade / SRE — requisito da disciplina

Precisa cobrir, no mínimo, os 5 pontos do enunciado:

- [x] **Tracing por nó** — LangSmith, mesmo caminho do assessor-ai: `LANGSMITH_TRACING`/
      `LANGSMITH_API_KEY`/`LANGSMITH_PROJECT` em `config/settings.py` (com default `False`/vazio pra
      não quebrar quem não tiver `.env`), propagadas pro `os.environ` logo após `settings = Settings()`
      (o SDK lê `os.environ` direto, `pydantic-settings` não é suficiente); tags/metadata
      (`user_id`/`session_id`) no `.invoke()` de `chat/runner.py`; `@traceable` em
      `chat/repositories.py` (`buscar_perfil`, `buscar_historico`, `salvar_mensagens`) pra cobrir a
      latência de Mongo que o auto-tracing do LangChain não pega, redigindo PII via
      `agents/nodes/guardrail/entrada.py:anonimizar_entrada` (mesmo `process_inputs`/`process_outputs`
      do assessor-ai) antes de mandar pro LangSmith Cloud. **Mesmo gap do assessor-ai:** o input cru do
      `guardrail_entrada_node` (auto-rastreado) ainda não passa pela redação — só o output
- [ ] **Latência interagentes e tempo total de resposta** — já disponível no dashboard do LangSmith
      (tracing acima cobre), falta só confirmar/consultar
- [ ] **Índice de erros** — contabilizar falhas de tool (`Response.error`), bloqueios de guardrail e
      reprovações do juiz que esgotam tentativas, como uma taxa sobre o total de turnos
- [ ] **Custo estimado para 100 e 1000 usuários/semana** — modelo simples: (tokens médios de
      entrada+saída por turno) × (preço por token de cada provider usado, `config/models.py`) ×
      (turnos médios por usuário/semana) × N usuários. Gemini/Groq têm tier gratuito com limite de
      requisições/minuto — a estimativa precisa considerar se 100/1000 usuários estourariam o tier
      grátis e o que isso custaria no plano pago
- [ ] **Custo/ROI e custo por resolução** — depende de definir o que conta como "resolução" (turno
      aprovado pelo Juiz sem bloqueio do guardrail, por exemplo) e um valor de referência de retorno
      (tempo economizado do usuário, redução de desperdício de alimentos via MoneySaving) pra
      justificar o ROI — decisão de produto, não só técnica, discutir com o time antes de implementar

## Redis e Qdrant — base implementada

Portado do assessor-ai (`tools/redis/{connection,schemas,perfil,chat}.py`,
`tools/qdrant/faq/{connection,schemas,core,ingest}.py`), mesmo padrão: client lazy com `global`,
funções simples sem classe. Não são requisito obrigatório da disciplina, mas somam pra "complexidade
do projeto" (item extra) e resolvem gaps reais.

- [x] **Redis — cache de perfil**: `tools/redis/perfil.py`, cache-aside sobre
      `tools/mongo/users` — `chat/repositories.py:buscar_perfil` tenta o Redis antes do Mongo,
      `encerrar_sessao` invalida a chave (perfil é reescrito nesse momento, ver
      `tools/mongo/chats/core.py:encerrar_sessao` → `perfis.atualizar_perfil`)
- [x] **Redis — rate limit de chat**: `tools/redis/chat.py:can_send_message`, mesmo limite do
      assessor-ai (10 mensagens/60s por usuário) — `chat/service.py:send_message` levanta
      `LimiteDeMensagensExcedido` quando estourado; `interfaces/tui/app.py:_processar` já tem
      `except Exception` ao redor do `send_message`, cai lá sem tratamento novo
- [x] **Qdrant — RAG do FAQ**: substituiu o FAISS local (`tools/faq_tools.py`, removido) por
      `tools/qdrant/faq/core.py:faq_retriever`, registrado em `tools/__init__.py` no lugar do antigo.
      **Divergência do assessor-ai:** `ingest.py` não fixa `_VECTOR_SIZE` (lá é `768`, hardcoded) —
      aqui o tamanho da collection é lido do embedding real (`len(vetores[0])`) porque
      `gemini-embedding-001` (mesmo modelo dos dois projetos) não documenta uma dimensão default
      fixa; hardcoded arriscava criar a collection com o tamanho errado sem estourar erro até o
      primeiro insert
- [x] `docker-compose.yml` com os dois serviços (`redis:7-alpine`, `qdrant/qdrant:latest`) +
      `config/docker.py` atualizado (`servicos_esperados`)
- [ ] **Rodar a ingestão** — `python -m frigus_ai.tools.qdrant.faq.ingest` precisa rodar uma vez
      contra o Qdrant local pra popular a collection `faq`; sem isso `faq_retriever` responde vazio.
      Não verificado nesta sessão (sem Docker/`.env` disponíveis no ambiente)
- [ ] **Fila de tasks — o caso de uso concreto apareceu: `encerrar_sessao`.** Os dois usos acima
      (cache, rate limit) são leitura/escrita síncrona simples, não fila. Mas
      `tools/mongo/chats/core.py:encerrar_sessao` faz **duas chamadas de LLM** (`_gerar_resumo` +
      `_gerar_perfil`) que o usuário espera só pra fechar o chat. É o único trabalho no projeto que
      não precisa estar no caminho da requisição — nenhuma resposta depende do resultado.
      **Ordem de ataque (não pular etapa):**
      1. `BackgroundTasks` do FastAPI na rota `DELETE /chats/{id}` (ver seção API acima) — zero infra
         nova, resolve 100% do problema observado. É por onde começar.
      2. Só subir pra fila de verdade (Redis Streams ou RQ) se aparecer requisito de **durabilidade**
         — job sobreviver a restart/crash do processo — ou mais de um worker. `BackgroundTasks` perde
         a task se o processo morrer no meio; hoje isso custa um resumo de conversa, não um dado de
         negócio.
      Os candidatos antigos (ingestão do Qdrant sob demanda, chamadas de MCP longas) seguem
      hipotéticos — não usar como justificativa
- [ ] **Cache do embedding de busca (Redis) — pendente, não implementada.** Hoje `faq_retriever`
      chama `embeddings.embed_query(question)` (API do Gemini) toda vez, mesmo pra pergunta repetida
      — nenhum cache entre a pergunta e o vetor. Cachear em Redis por hash da pergunta normalizada
      (chave `faq:embedding:<hash>`, TTL similar ao `PROFILE_TTL_TIME`) evitaria a chamada de API
      repetida no caso comum de FAQ (poucas perguntas frequentes). Mesmo raciocínio de custo já
      aplicado à Spoonacular (ver seção acima) — decidir TTL/tamanho antes de implementar, não é
      óbvio que compensa a complexidade pro volume atual de perguntas de FAQ
- [ ] **Em discussão:** remover o agente `faq` (`agents/nodes/faq.py` + `faq_app` em `graph/agents.py`)
      e deixar só a tool — o Roteador identifica que é pergunta de FAQ e chama `faq_retriever` direto,
      igual já acontece com `estoque`/`compras`/`financeiro` (nó chama a tool, `orquestrador` formata
      em linguagem natural, `juiz` valida). Não faz sentido pagar uma chamada de LLM extra só pra
      decidir usar a única tool que o agente FAQ tem — o Roteador já tomou essa decisão. Efeito
      colateral: reduz de 10 pros 9 nós no grafo (ainda bem acima do mínimo de 5 agentes exigido)
- [ ] Pelo menos um teste pro cache-aside de perfil (hit vs. miss, mockando `tools/redis/connection.py`)
      — ainda sem teste de `chat/repositories.py` no geral (ver seção "Testes" abaixo)

### Async — decisão tomada, migração em duas fases (agentes → API)

Ver plano completo em `C:\Users\davifranco-ieg\.claude\plans\async-napping-bentley.md`. Postgres
(psycopg2) e Mongo (pymongo) continuam síncronos — trocar driver é decisão maior, fora de escopo
(ver "ODM — avaliado, descartado" abaixo, mesmo raciocínio). Ganho real não é latência por request
(chamada de LLM domina de qualquer jeito), é teto de concorrência + terreno pronto pra SSE/A2A/MCP.

- [x] **Fase 1 — agentes/grafo async.** Os 10 nós de `agents/nodes/` viraram `async def`,
      chamando `.ainvoke()` nos `*_app` de `graph/agents.py` e nos `llm_*.invoke` diretos
      (`juiz.py`, `guardrail/{entrada,saida}.py`). `chat/runner.py:executar` também é `async def`
      agora (`await fluxo_agentes().ainvoke(...)`). Tools (`ESTOQUE_TOOLS` etc.) não mudaram — sync
      continua funcionando via offload automático do LangChain pra thread (ver entrada nova em
      `.agents/skills/langchain.md`). `chat/service.py:send_message` tem uma ponte provisória
      (`asyncio.run(runner.executar(...))`) até a Fase 2 sair. `pytest-asyncio` entrou como dev dep
      (`asyncio_mode = "auto"` em `pyproject.toml`). Verificado: `just test` (63 passed) e
      `just check` limpos
- [ ] **Fase 2 — API e interfaces.** `chat/service.py`/`chat/repositories.py` viram async de vez
      (repositories embrulha pymongo com `asyncio.to_thread`, sem trocar driver), rotas de
      `interfaces/api/routes/` viram `async def`, `interfaces/tui/app.py:_processar` troca
      `@work(thread=True)` por worker async nativo do Textual. `.agents/skills/fastapi.md`
      ("Divergências deliberadas" — rotas `async`) precisa ser reescrito junto, já que a decisão que
      documenta deixa de valer

## Spoonacular — client + tabela de lookup de ingredientes

Ver `.agents/skills/spoonacular.md` pros 6 endpoints que vamos consumir (Ingredient Search, Get
Ingredient Information, Search Recipes by Ingredients/Nutrients, Get Recipe/Similar Information) e o
motivo de cache ser obrigatório (tier gratuito: 50 pontos/dia). Tabela de lookup fica em Mongo, não
Postgres — schema `dataload` é fornecido pela disciplina e compartilhado com outras apps do projeto,
não faz sentido criar tabela lá pra algo que só o frigus-ai usa; o dado (`spoonacular_id ↔
estoque_item_id`) também não tem relação nenhuma pra justificar relacional.

### ODM (MongoEngine/Beanie) — avaliado, descartado

`tools/mongo/{chats,users}` já usam `@dataclass` + `asdict()` puro contra `pymongo`, sem ODM — é o
padrão estabelecido, duas vezes. Motivo de não trocar: Pydantic aqui é reservado pra schema de tool
exposta ao agente (`args_schema=` do `@tool`, ver `tools/postgres/*/schemas.py`); `chats`/`users` não
são tool, são storage interno, e `@dataclass` marca essa diferença. A tabela de lookup é o mesmo
caso — ninguém expõe ela pro agente.

Se algum dia justificar adotar um ODM de verdade (mais domínios Mongo, dor real de mapear dict à
mão): **MongoEngine**, não Beanie. Beanie é async, construído em cima do `motor` — trocaria o driver
síncrono (`pymongo`) que todo o resto do projeto usa por design (I/O é síncrono de propósito, ver
`.agents/skills/fastapi.md`). MongoEngine é síncrono, plugaria ao lado do `pymongo` que já existe
sem duplicar driver.

### Plano de implementação

- [x] `uv add httpx` — client HTTP, nenhum ainda existia no projeto (ver `other-tools.md`).
      `.venv` criado (`py -3.13 -m venv`, mesmo padrão do `justfile`), `uv sync` rodado — `uv.lock`
      atualizado de verdade, `ruff check` limpo, `pytest` 48 passed
- [x] `SPOONACULAR_API_KEY` em `config/settings.py` + `.env.example`, com default `""` (mesmo padrão
      de `LANGSMITH_API_KEY`/`ANTHROPIC_API_KEY`) — não quebra quem não tiver a var enquanto os
      passos abaixo não terminam
- [x] `tools/spoonacular/connection.py` — client `httpx` configurado uma vez (base URL, `apiKey`
      como default param, mesclado em toda chamada). Eager no import (mesmo padrão de
      `tools/mongo/connection.py`) porque `httpx.Client()` não abre socket no construtor — diferente
      de `tools/postgres/connection.py`, onde o `ThreadedConnectionPool` abre conexão de verdade e
      por isso precisa do getter lazy com `global _pool`
- [x] `tools/spoonacular/schemas.py` — Pydantic (`args_schema` de tool, essas sim chamadas pelo
      agente), uma classe por endpoint do `spoonacular.md`. **Simplificação deliberada:** cortou
      `sort`/`sortDirection`/`offset` de `SearchIngredientsArgs` e `addWinePairing`/`addTasteData`
      de `GetRecipeInformationArgs` — não servem o caso de uso "receita com o que tem no estoque",
      YAGNI. **Default diferente do documentado na API:** `ranking=2` (minimiza faltando, não 1) e
      `ignore_pantry=True` (não `False`) em `FindRecipesByIngredientsArgs` — o default da API é
      genérico, o do produto é "o que dá pra fazer com o que já tenho"
- [x] `tools/spoonacular/core.py` — `find_recipes_by_ingredients` e `get_recipe_information`,
      `@tool` + `@log_tool`. Cache com **TTL de 1h** (exigência do ToS da Spoonacular): a janela
      horária (`int(time.time()) // 3600`) entra na chave do `lru_cache`, então a entrada velha é
      descartada sozinha — sem cache externo. `number` limitado a `ge=1, le=10` (default 5) pra não
      queimar a cota de 50 pontos/dia
- [ ] `tools/mongo/spoonacular/schemas.py` — `IngredienteMatchDocument` (`@dataclass`, ver sketch já
      discutido no chat)
- [ ] `tools/mongo/spoonacular/core.py` — `buscar_match(spoonacular_id)` / `salvar_match(...)`; toda
      tool acima que resolve ingrediente passa por aqui antes de gastar ponto de API
- [x] Registrar a(s) tool(s) no agente `receitas` — em `tools/__init__.py:RECEITAS_TOOLS`.
      **Junto veio um bug de produto:** o prompt mandava passar "os itens do estoque" pra
      `find_recipes_by_ingredients`, mas `match_recipes_to_stock` só devolve contagens (não os nomes
      dos ingredientes) e o agente não tinha `query_stock`. Sem fonte pros nomes, o LLM só podia
      inventar. Resolvido adicionando `query_stock` ao `RECEITAS_TOOLS` (tool que já existia) e
      corrigindo `prompts/receitas.md` — **não** criando tool composta nova
- [ ] Atualizar tabela de tools no README.md
- [x] Teste em `tests/tools/spoonacular/test_core.py` — mocka a chamada HTTP, cobre mapeamento de
      resposta, erro 402 (cota) e **expiração do cache na virada da janela** (verificado por mutação:
      sem a janela na chave, o teste falha)
- [ ] Atualizar `.agents/skills/spoonacular.md` — a seção "Pegadinhas deste repo" ainda diz "client
      não implementado", e os endpoints `/food/products/*` avaliados depois (resolução de produto)
      não estão documentados lá. Ver a decisão abaixo antes de escrever

### Resolução de produto (`/food/products/*`) — avaliado, adiado

Desenho considerado: `resolver_produto(codigo_barras | nome)` devolvendo
`encontrado | confirmacao_necessaria | nao_encontrado`, separando `product_id` interno do
`spoonacular_product_id`. **Adiado por dois motivos concretos:**

1. **Não existe código de barras no sistema.** `grep -riE "upc|barcode|ean|gtin"` não acha nada;
   `data/sql/schema.sql:products` é `id, name, category, storage_place, unit_price`; a única origem
   plausível (`register_purchase_from_nfe`) é stub que retorna erro. O branch de UPC nasceria morto.
2. **A cota não comporta.** `search` + `products/{id}` + `classify` = ~3 pontos **por produto**; uma
   compra de 15 itens consome 45 dos 50 pontos/dia. Não é problema de afinar TTL, é aritmética.

Vale registrar também: `/food/products/*` é catálogo de embalados de marca do mercado americano —
o mesmo motivo pelo qual não usamos "preço de produtos comparáveis" no MoneySaving (base
estrangeira) invalida o catálogo como fonte de despensa brasileira. Se um dia houver resolução de
ingrediente, o caminho é `/ingredients/search` (genérico, 1 ponto), que o skill file já documenta.
`Analyze Recipe` também fica fora: aceita receita só em inglês/alemão, exigiria tradução antes.

**Reavaliar quando:** a leitura de NF-e sair do stub (aí existe código de barras de verdade).

## OpenRouter como terceiro provider — implementado

`config/models.py` ganhou `openrouter` nas três tabelas (`PROVIDER_MAP`, `API_KEYS`, `BUILDERS`).
OpenRouter fala o protocolo da OpenAI, então o builder é
`partial(ChatOpenAI, base_url="https://openrouter.ai/api/v1")` — `build_llm` não precisou de nenhum
`if provider ==` novo.

- [x] `uv add langchain-openai`; `OPENROUTER_API_KEY` em `config/settings.py` + `.env.example`
      (default `""`, mesmo padrão de `ANTHROPIC_API_KEY`)
- [x] **`build_llm` devolve `None` quando o provider não tem API key.** `ChatOpenAI` valida a chave
      no construtor (diferente de Gemini/Groq/Anthropic), então sem isso o import quebraria pra quem
      não configurou. De quebra corrige uma inconsistência que já existia: `ANTHROPIC_API_KEY` tem
      default `""` e `build_llm(model=CLAUDE_SONNET)` construía um cliente com chave vazia que só
      falharia na primeira chamada
- [x] Cadeia: `llm_especialista = gemini → groq → openrouter` (o terceiro só entra se configurado)
- [x] `tests/graph/test_llm.py` — resolução do provider, `None` sem chave, e o fallback com 2 elos
      quando a chave existe
- **Modelo escolhido:** `z-ai/glm-5.2:free`. O catálogo `:free` **rotaciona** — hoje não há mais
      llama/deepseek/qwen gratuitos. Ao trocar, confirmar em <https://openrouter.ai/models> que o
      modelo suporta **tool calling**, que `llm_especialista` exige

## Neo4j — grafo de recomendação de receitas (avaliado)

Modelagem exploratória em `tools/neo4j/{nodes,edges,queries}.cypher` (`User`/`Ingredient`/`Recipe`,
`PREFERS`/`DISLIKES`/`ALLERGIC_TO`/`REQUIRES`/`SIMILAR_TO`) — por enquanto é só script Cypher solto,
sem `connection.py`/tool nenhuma. Responde a pergunta #3 de "Perguntas em aberto" mais abaixo: Neo4j
segue no roadmap, mas o propósito mudou de "auditoria de chamadas agente-a-agente via Cypher" (nota
antiga em "Faltando", mais abaixo) pra "grafo de preferência/recomendação de receita".

- [ ] Avaliar <https://neo4j.com/labs/agent-memory/tutorials/first-agent-memory/> como base da
      memória de longo prazo do agente (hoje ⚠️ parcial — só resumo de perfil em `tools/mongo/users`,
      ver tabela de requisitos no AGENTS.md). O tutorial modela memória episódica/semântica como
      grafo; se adotado, o grafo `User`-`Ingredient`-`Recipe` acima vira o mesmo grafo de memória, não
      uma segunda base separada — `PREFERS`/`DISLIKES`/`ALLERGIC_TO` já são memória semântica de
      usuário por natureza
- [ ] Fecha com Spoonacular: hoje o grafo só tem as 2 receitas de exemplo do sketch; nós reais de
      `Ingredient`/`Recipe` poderiam ser povoados a partir das respostas da API (Ingredient Search /
      Get Recipe Information) em vez de só a tabela de lookup Mongo (ver seção "Spoonacular" acima) —
      mas só decidir depois de `tools/spoonacular/core.py` estar rodando de verdade, não adiantar
      infra nova sem dado real pra povoar
- [ ] Decidir se compensa um banco a mais (Postgres + Mongo + Neo4j, além de Redis/Qdrant ainda
      pendentes) só pra esse grafo, ou se dá pra modelar a mesma coisa em Mongo (documento com arrays
      de preferência). Neo4j ganha em travessia tipo "receitas cujos ingredientes obrigatórios não
      cruzam com o que o usuário é alérgico/não gosta" (última query de `queries.cypher`), que é
      consulta recursiva cara em documento — vale confirmar se esse tipo de consulta é usado de
      verdade antes de subir infra
- [ ] **Bloqueador antes de tudo acima: não existe fonte de dado pra povoar o grafo.**
      `PREFERS`/`DISLIKES`/`ALLERGIC_TO` são o que dá valor ao Neo4j (só a última query de
      `queries.cypher` — receitas que não cruzam com alergia/desgosto — justifica banco de grafo; o
      resto são lookups que Postgres/Mongo já fazem). Mas alergia e preferência **não são campo em
      lugar nenhum do sistema**: `data/sql/schema.sql` não tem coluna pra isso, e o perfil em
      `tools/mongo/users` é texto livre gerado por LLM (`prompts/perfil.md`), não dado estruturado.
      Subir Neo4j antes disso é infra sem dado — mesmo erro de construir resolução de produto por
      código de barras sem código de barras no sistema. **Pré-requisito:** extrair preferência
      estruturada (do perfil ou de um cadastro explícito) e ter onde guardá-la. Só depois decidir
      Neo4j vs. array em documento Mongo
- [ ] Se seguir: novo serviço no `docker-compose.yml`, `tools/neo4j/connection.py` (driver oficial
      `neo4j`, lazy igual às outras conexões) e `tools/neo4j/core.py` com as tools de fato

## Alembic e ORM — avaliado, ainda não priorizado

Postgres hoje é acessado via `psycopg2` cru (SQL inline em cada `core.py`, `next_id` calculando ID
manualmente porque o schema fornecido não é serial — ver AGENTS.md "Stack"). O assessor-ai já resolveu
isso com **SQLAlchemy + Alembic** (ver "Estado real do assessor-ai" mais abaixo) — migrations
versionadas em vez de depender só do `data/sql/schema.sql` fornecido pronto pela disciplina.

- [ ] Confirmar se compensa pro Frigus antes de começar: o schema `dataload` é fornecido pela
      disciplina e compartilhado com outras apps do grupo — migrar pra Alembic significa este repo
      passar a "dono" das migrations do schema, o que só faz sentido se o time concordar que é assim
      daqui pra frente, não só consumidor de um schema pronto
- [ ] Se seguir: models SQLAlchemy por domínio (`estoque`, `compras`, `receitas`, `financeiro`),
      trocando as queries cruas de `tools/postgres/*/core.py` um domínio por vez — não precisa ser
      reescrita atômica
- [ ] `alembic init` + primeira migration como baseline do `data/sql/schema.sql` atual (gerar a partir
      do schema existente e `alembic stamp head`, não recriar do zero)
- [ ] Reavaliar `next_id` (`tools/postgres/helpers.py`) — com Alembic dá pra decidir se vale migrar as
      PKs pra serial/identity de verdade, em vez de manter `MAX(id)+1` manual

**Não bloqueia nada hoje.** SQL cru funciona; isso é redução de risco (menos SQL manual espalhado,
histórico de schema versionado), não requisito da disciplina.

## Testes — suíte base + CI concluídos

`tests/` espelha a estrutura do pacote (mesmo corte do assessor-ai). 48 testes, rodam em ~4s, sem
tocar banco nem LLM.

- [x] `pytest` e `ruff` como dev dependencies (`[dependency-groups] dev`)
- [x] `tests/tools/test_response.py` — `Response.ok`/`Response.error` (incl. `Exception` virando str)
- [x] `tests/tools/postgres/test_helpers.py` — `normalize_enum` (case/acento/espaço, sem
      correspondência, valor vazio), `compute_product_status` (limites exatos do semáforo:
      vencido / vence hoje / `DIAS_ATENCAO` / primeiro dia fresco) e `expiring_date_threshold`.
      `next_id`/`resolve_stock_id` ficaram de fora — precisam de cursor real, são teste de integração
- [x] `tests/agents/nodes/guardrail/test_entrada.py` — caminhos determinísticos do guardrail, sem
      LLM: `_detectar_injecao`, `_detectar_acesso_interno`, precedência entre os dois,
      `anonimizar_entrada` (CPF/email/telefone/senha, reversibilidade pelo mapa, texto sem PII) e
      `_extrair_categoria` (incl. o fallback deliberado pra `APROVADO` quando o LLM foge do formato)
- [x] `tests/conftest.py` com env vars fake. **Achado (o mesmo do assessor-ai):**
      `frigus_ai/tools/__init__.py` importa os cores das tools, que puxam a cadeia até
      `config/settings.py:Settings()` — validado no import. Ou seja, até um teste de função pura
      quebrava na *coleção* sem `GEMINI_API_KEY`/`GROQ_API_KEY`/`POSTGRES_URI`. Resolvido no
      `conftest.py` (com `setdefault`, pra não atropelar `.env` local) em vez de espalhar valores
      dummy no YAML do CI — assim a suíte roda sem `.env` em qualquer lugar
- [x] `.github/workflows/ci.yml` — push/PR pra `main`: `uv sync --locked` → `ruff check .` → `pytest`
- [x] `[tool.ruff]` no `pyproject.toml`. **Achado:** sem config própria, o ruff subia a árvore de
      diretórios e herdava regras de fora do repo — resultado não reprodutível entre máquinas/CI.
      Fixado `target-version = "py313"` + `ignore = ["BLE001", "SIM117", "DTZ011"]` (cada um com o
      motivo comentado no arquivo). Os 128 achados restantes foram corrigidos (`ruff check --fix`
      pros automáticos; `check=False` explícito nos `subprocess.run` de `config/docker.py`, que
      inspecionam `returncode`/stdout de propósito, e `dict()` → literal em `graph/llm.py`).
      `ruff check .` passa limpo hoje

- [ ] **Ainda sem teste:** `chat/` (service/runner com o grafo mockado — o assessor-ai tem esse
      padrão pronto em `tests/chat/`), `tools/mongo/`, `tools/postgres/{estoque,compras,receitas,
      financeiro}/core.py`, e os nós além do guardrail de entrada (`router`, `juiz`, `orquestrador`,
      `graph/builder.py`). Priorizar `chat/` e `juiz` — são os que concentram lógica de decisão
- [ ] Decidir separação `tests/unit/` vs. `tests/integration/` antes da suíte crescer, ou manter
      achatado enquanto for pequena
- [x] **Convenção adotada:** "toda feature nova vem com pelo menos um teste", registrada em
      `AGENTS.md` (seção "Fluxo de trabalho") como norma de PR, **não** como gate automático de CI.
      Motivo: agora que a suíte base existe, a convenção tem no que se apoiar — mas travar PR por
      cobertura antes de `chat/` e os nós estarem cobertos seria fricção sem rede de segurança
      proporcional. Promover a gate obrigatório quando os itens acima saírem
# TODO — frigus.ai

Baseado no estado real do repo (`README.md` em `main`, commit atual: 7 commits). Este documento separa o que já
está implementado do que falta, e documenta a decisão em aberto restante: integração com o `assessor-ai`
(localização da API já decidida — mesmo repo, ver seção abaixo).

---

## Implementado

- **Grafo completo (LangGraph)**: Guardrail Entrada → Router → 5 especialistas (Estoque, Compras, Receitas, FAQ,
  Financeiro) → Orquestrador (Estoque/Compras/Financeiro) ou direto pro Juiz (Receitas/FAQ) → Juiz →
  Guardrail Saída.
- **Juiz (LLM-as-judge)**: audita grounding, relevância e completude; devolve pro especialista de origem em
  caso de reprovação, até 2 tentativas, depois segue mesmo reprovado (loga aviso).
- **Guardrail de Entrada**: detecção determinística de prompt injection, anonimização de PII, classificação
  LLM (aprova / bloqueia por ofensivo, perigoso, ilícito, político, conselho médico).
- **Guardrail de Saída**: nunca bloqueia — redige PII residual e corrige afirmações de segurança
  alimentar/validade sem ressalva.
- **5 domínios funcionais**: Estoque (CRUD + semáforo de validade), Compras (lista + sugestões automáticas via
  `minimal_quantity`), Receitas (cruza estoque real x banco de receitas), Financeiro/MoneySaving (gastos
  mensais, comparação entre meses, valor de alimentos descartados, evolução do desperdício), FAQ (RAG via
  FAISS sobre `Frigus-Documentacao.pdf`).
- **Multi-tenancy via `contextvars`**: `current_user_id` / `current_stock_id` em `tools/postgres/context.py`.
- **Persistência**: Postgres (schema `dataload`, IDs não-seriais resolvidos via `next_id` = `MAX(id)+1`),
  MongoDB (`agent_chats` para histórico da conversa do bot, `user_profiles` para perfil comportamental gerado
  pela IA), checkpointing de grafo via `MemorySaver` (em memória).
- **UI de terminal** (Rich + pyfiglet) e `docker-compose.yml` (Postgres + Mongo), com auto start/stop via
  `config/docker.py`.

## Faltando (placeholders no repo, só `__init__.py`)

- [ ] **`tools/redis/`** — decidir o uso primeiro: rate limit (`can_send_message`), cache, ou trocar o
      `MemorySaver` por checkpointer persistente. São três usos concorrentes pelo mesmo Redis — definir
      prioridade de implementação.
- [ ] **`tools/qdrant/`** — migrar RAG do FAISS local para Qdrant, e implementar a busca semântica de
      receitas. **Nota:** o README atual não menciona Qdrant nem cache semântico (`cache_respostas`) —
      isso ainda é só plano, o RAG de FAQ hoje roda 100% em FAISS local. Vale confirmar se a migração é
      prioridade ou fica pra depois do MVP.
- [ ] **`mcp_server/`** — expor as tools do Frigus para hosts MCP (Claude Desktop etc.).
- [ ] **`a2a_server/`** — expor o grafo do Frigus como agente A2A para outros sistemas. (Ver seção abaixo —
      isso é sobre o Frigus **oferecer** um endpoint A2A, não sobre consumir o assessor-ai.)
- [x] **Neo4j** — atualizado: propósito mudou de auditoria de chamadas agente-a-agente pra grafo de
      recomendação de receitas (preferência/alergia de usuário × ingrediente × receita). Modelagem
      exploratória em `tools/neo4j/*.cypher`, avaliação completa na seção "Neo4j" acima.
- [ ] **LangSmith** — mesma situação: não referenciado no repo. Se for pra observabilidade, é config de
      ambiente (`LANGCHAIN_TRACING_V2`, etc.), não exige mudança estrutural — mas precisa ser adicionado.
- [ ] **Testes automatizados** — não há pasta `tests/` na estrutura listada. Nada de PromptBreaker/pytest
      layer pros guardrails ainda.
- [ ] **API HTTP (FastAPI)** — existe uma pasta `api/` no repo, mas o `README` não descreve o que tem lá nem
      documenta rotas. Preciso ver o conteúdo real de `api/` pra saber se é esqueleto ou já funcional — não
      dá pra confirmar pelo README.

---

## Decisão: assessor-ai — A2A ou MCP?

> **Atualizado** — a versão real do `assessor-ai` é bem mais madura do que a snapshot que eu tinha visto
> antes (fetch anterior pegou algo desatualizado/cacheado). Isso não muda a resposta, mas muda o "como".

### Estado real do assessor-ai (README atual)

- **Camada de serviço própria** (`chat/service.py`): `create_chat`, `send_message`, `get_history`,
  `encerrar_sessao` — já é uma API pública desenhada pra ser consumida por múltiplas interfaces.
- **3 interfaces já rodando sobre essa camada**: terminal, TUI (Textual) e **API HTTP (FastAPI)**, com
  auth por `X-API-Key` e rate limit por IP (slowapi).
- **Checkpointing persistente** (`MongoDBSaver`, não mais `MemorySaver`) — estado do grafo sobrevive a
  restart, ao contrário do Frigus hoje.
- **Redis em produção de verdade**: rate limit por `user_id` (`can_send_message`), cache de
  `perfil_usuario` (TTL 1h, invalidado ao encerrar sessão) e hash de API keys — as três coisas que o
  Frigus ainda só cogitou.
- **Qdrant com conexão provisionada**, mas **ainda sem tool usando** — RAG do FAQ continua em FAISS local
  lá também. Ou seja, nesse ponto os dois projetos estão no mesmo estágio (conexão pronta, migração RAG
  não feita).
- **SQLAlchemy + Alembic** — migrations versionadas, não é mais SQL cru/psycopg2 puro.
- **LangSmith já ligado** (opcional via env var), com uma limitação documentada que vale copiar: o nó de
  guardrail de entrada auto-rastreado loga a mensagem crua do usuário como input, porque a anonimização
  só acontece no *output* do nó — só os pontos com `@traceable` manual redigem PII no input também. Bom
  lembrete pro guardrail do Frigus quando vocês ligarem tracing lá.

Isso **não muda a resposta A2A** — o assessor-ai continua sendo um agente completo e independente, e
não faz sentido reduzir ele a tools MCP soltas e perder toda essa orquestração (guardrail, checkpointing,
compliance). Mas muda o caminho pragmático de curto prazo:

### Contrato real da API (via `openapi.json`, `assessor-ai.fastapicloud.dev`)

Confirmado direto do schema — só existem 3 rotas de negócio, todas em nível de **conversa**, nenhuma em
nível de **tool**:

| Rota | O que faz | Corpo |
|---|---|---|
| `POST /v1/keys` | Provisiona `user_id` + `api_key` novos | `{ "nome": str, "email": str }` |
| `POST /v1/chats` | Cria (ou retorna) a sessão do usuário autenticado | sem corpo — usuário vem da auth |
| `POST /v1/chats/{chat_id}/messages` | Manda uma mensagem (até 4000 chars) pro agente | `{ "content": str }` → responde `{ chat_id, content }` |
| `GET /v1/chats/{chat_id}/messages` | Histórico do chat | — |

**Implicação importante pro caso de agenda via MCP que discutimos**: essa API só expõe o agente
conversacional completo — não tem `POST /v1/events` nem nada granular. Ou seja, não dá pra usar essa API
HTTP como base pra tools MCP de agenda; um servidor MCP real ainda precisaria ser construído em cima de
`tools/postgres/agenda/core.py` diretamente. São dois trabalhos de integração diferentes, um não
reaproveita o outro.

**Ambiguidade a checar antes de integrar**: no `securitySchemes` do schema só aparece um `APIKeyHeader`,
com o header `X-Signup-Secret` — e ele é referenciado tanto em `POST /v1/keys` quanto nas rotas de chat.
O README menciona `X-API-Key` pra uso normal (via `get_current_user`), então ou o schema gerado juntou dois
`Security()` distintos sob o mesmo nome (bug de doc, comum no FastAPI quando duas dependências têm o mesmo
nome de classe), ou as rotas de chat realmente aceitam o signup secret também. Vale confirmar em
`interfaces/api/auth.py` / `gen_key.py` antes de codar o cliente — não dá pra confiar 100% no
`openapi.json` pra esse detalhe específico.

### Duas rotas possíveis, não uma só

1. **Curto prazo / MVP: chamar a API HTTP que já existe.** O assessor-ai já expõe
   `interfaces/api/routes/chats.py` com auth por API key funcionando de verdade. Nada impede o nó
   Financeiro do Frigus de simplesmente fazer uma chamada HTTP autenticada pra esse endpoint hoje —
   não é A2A formal (sem Agent Card, sem discovery), mas é o caminho de menor esforço e já usa a API que
   está pronta.
2. **Longo prazo / se precisar de interoperabilidade real: formalizar como A2A.** Só compensa o esforço
   extra (Agent Card, protocolo de discovery) se a ideia é o Frigus (ou outros agentes) descobrirem e
   conversarem com múltiplos agentes de forma padronizada, não só com o assessor-ai fixo. Pra uma
   integração ponto-a-ponto entre dois projetos de vocês, é overhead que talvez não pague o custo agora.

Vale decidir isso primeiro: se o objetivo é só "o Frigus usa o assessor-ai", a rota 1 entrega o mesmo
resultado funcional com muito menos código. Se o objetivo do curso/projeto é especificamente demonstrar
A2A como conceito (parece que é, já que tem `a2a_server/` reservado no Frigus), aí faz sentido ir de
vez pra rota 2.

### O que falta pra qualquer uma das duas rotas

1. **`assessor-ai` não tem servidor A2A hoje** — só a API FastAPI. Pra rota 2, precisa adicionar
   exposição A2A (Agent Card, endpoint de invocação) por cima da camada `chat/service.py` que já existe
   — na real é bem menos trabalho do que eu achava antes, porque a lógica de serviço já está desacoplada
   das interfaces (é literalmente adicionar mais uma interface, igual foi feito com TUI/API).
2. **O `a2a_server/` do Frigus é pra outra coisa** — ele é pro Frigus **oferecer** um agente A2A pra fora,
   não pra **consumir** o assessor-ai. Pra chamar o assessor-ai (rota 1 ou 2), o ponto de integração é
   dentro do nó Financeiro do Frigus, chamando pra fora — não o `a2a_server/`.
3. **Identidade/multi-tenancy entre os dois sistemas.** O assessor-ai autentica por API key
   (`X-API-Key` → `get_current_user`) e tem seu próprio conceito de usuário (Postgres + Mongo dele). O
   Frigus tem o próprio `current_user_id` via `contextvars`. Alguém precisa decidir como um usuário do
   Frigus vira um usuário (ou uma API key) no assessor-ai — criar conta automaticamente na primeira
   chamada? Mapear 1:1 por e-mail? Isso é trabalho de integração de verdade, independente de A2A ou API
   direta.
4. **Os domínios "Financeiro" não são o mesmo domínio.** Continua sendo o ponto que mais merece atenção:
   o Financeiro do Frigus é **MoneySaving** — gastos mensais, valor de alimentos descartados, desperdício
   ao longo do tempo, derivado do estoque. O Financeiro do assessor-ai é um **ledger pessoal genérico**
   (`add_transaction`, `query_transactions`, saldo, categorias tipo comida/transporte/lazer) — não sabe
   nada sobre desperdício, validade, ou o schema `dataload`.
   - Se a ideia é trocar de vez "cálculo de desperdício" por "chat de finanças pessoais genérico", tudo
     bem, é decisão de produto.
   - Se a ideia é manter o MoneySaving (que já funciona, com dados reais de estoque) e só pegar o
     *mecanismo* de orquestração do assessor-ai, isso não rola sem adaptar as tools financeiras pro
     schema do Frigus — vira reescrita, não integração.

### Tarefas concretas

**Financeiro** (pode usar a API HTTP que já existe hoje):

- [ ] Confirmar header de auth real (`X-API-Key` vs `X-Signup-Secret`) em `interfaces/api/auth.py` do
      assessor-ai antes de codar o cliente
- [ ] Decidir rota 1 (chamar API existente) vs. rota 2 (formalizar A2A) — depende do objetivo ser
      "funcionar" ou "demonstrar A2A" pro curso
- [ ] Definir qual dos dois cenários de domínio financeiro é o real (trocar escopo do MoneySaving vs.
      reaproveitar só o mecanismo de orquestração)
- [ ] Resolver identidade cross-sistema: no primeiro contato de um usuário do Frigus, chamar
      `POST /v1/keys` com nome/e-mail dele, guardar o `api_key` retornado associado a esse usuário no
      Frigus, e usar essa chave nas chamadas de chat seguintes
- [ ] Se for rota 2: adicionar exposição A2A no `chat/service.py` do assessor-ai + cliente A2A no nó
      Financeiro do Frigus
- [ ] Decidir se o resultado do assessor-ai ainda passa pelo Orquestrador do Frigus antes do Juiz, ou se
      pula direto pro Juiz (equivalente ao fluxo de Receitas/FAQ)

**Agenda** (não tem atalho — a API HTTP não ajuda aqui, é trabalho novo dos dois lados):

- [ ] Construir `mcp_server/` no assessor-ai expondo `add_event`, `query_events`, `query_daily_events`,
      `update_event` (de `tools/postgres/agenda/core.py`) como tools MCP — a API REST atual não serve de
      base pra isso, é código novo
- [ ] Definir como cada chamada de tool recebe o `user_id` (a API REST resolve isso pela auth; MCP
      cru não tem esse conceito — precisa vir como parâmetro explícito ou algum mecanismo de sessão)
- [ ] Adicionar domínio Agenda no Frigus: prompt novo, nó novo, entrada no Router — hoje não existe
- [ ] Cliente MCP no novo nó Agenda do Frigus

---

## Decisão: API no mesmo repo ou separado?

**Resposta: mesmo repo — confirmado.** Motivos:

- Projeto acadêmico, escopo pequeno, provavelmente mantido por poucas pessoas
- API, grafo e tools compartilham o mesmo ciclo de vida e o mesmo deploy
- Separar repo cedo cria overhead de sincronizar versões, CI duplicado e dependências cruzadas sem
  nenhum ganho real nesse estágio

Só valeria separar se a API precisasse de deploy/versionamento independente do grafo, ou se times diferentes
fossem mexer em cada parte — nenhum dos dois parece ser o caso aqui. Implementação vai em
`interfaces/api/` (pasta `api/` do root não existe mais desde o refactor pra `src/`), seguindo o
padrão do assessor-ai — ver seção "API (FastAPI/Flask)" acima.

---

## Perguntas em aberto (preciso da sua resposta antes de codar)

1. O domínio Financeiro do assessor-ai vai **substituir** o MoneySaving atual, ou os dois vão coexistir
   (MoneySaving fica, e o assessor-ai cobre um financeiro pessoal mais amplo)?
2. Prioridade entre Redis (rate limit vs. cache vs. checkpointer) — qual entra primeiro?
3. ~~Neo4j e LangSmith ainda estão no roadmap ou foram descartados nessa fase do projeto?~~ —
   respondido: LangSmith já está ligado (ver "Observabilidade / SRE" acima); Neo4j segue no roadmap
   com propósito atualizado (ver seção "Neo4j" acima)
