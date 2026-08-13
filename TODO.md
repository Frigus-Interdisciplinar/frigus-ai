# TODO

Próximos passos planejados. Contexto do projeto e checklist de requisitos da disciplina em
[AGENTS.md](AGENTS.md).

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
`ANTHROPIC_API_KEY`, `DATABASE_URI`, `MONGODB_URI`) — nenhum campo faltando. O que falta é o env
**final**, que só fica completo conforme as features pendentes entrarem. Já documentado como
comentário no `.env.example` pra não virar surpresa:

- [ ] `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` — entram com a seção de
      Observabilidade
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

## Seleção interativa de interface (questionary) — avaliado, adiado

`main.py` hoje só resolve `terminal` (`python main.py terminal`). Ideia: quando existir mais de uma
interface real (`tui`, `api`, eventualmente frontend), usar `questionary.select(...)` pra menu de
seta em vez de exigir o nome exato como argumento — reduz fricção pra quem não decorou os comandos.

- [ ] Adicionar `questionary` como dependência **só quando o segundo modo existir de verdade** (hoje
      só tem 1 opção, não há o que selecionar — YAGNI). Desenho: `python main.py <interface>` continua
      funcionando direto (scriptável, usado por CI/automação); `python main.py` sem argumento cai no
      menu interativo do `questionary` como atalho amigável — as duas formas convivem, não é
      substituição

## API (FastAPI/Flask) — requisito da disciplina, localização pendente

**Decisão em aberto:** a API fica neste mesmo repositório (`api/` já existe como placeholder) ou
vira um repositório separado que consome este projeto como dependência/serviço? Não implementar
nada em `api/` antes dessa decisão — avaliar com o time:

- Mesmo repo: mais simples de desenvolver e entregar pra disciplina, reusa `chat/service.py`
  (refactor acima) direto, sem versionar/publicar nada
- Repo separado: força a API a ser um cliente de verdade do domínio (via lib publicada ou HTTP
  interno), mais "arquitetura de produção", mas overhead desnecessário pro prazo da disciplina

Depois da decisão, seguir o padrão do assessor-ai (`interfaces/api/`): `main.py` (app FastAPI),
`auth.py` (se precisar de API key), `routes/` por recurso (`chats`, `health`), `schemas/` (Pydantic
de request/response). Rotas chamam só o módulo de serviço, nunca o grafo ou as tools direto.

- [ ] Decidir localização (mesmo repo vs. repo separado)
- [ ] Esqueleto de rotas: `POST /chats`, `POST /chats/{id}/messages`, `GET /chats/{id}/messages`
- [ ] Controle de sessão por usuário de verdade (hoje é só `thread_id` gerado em memória no
      terminal) — ver item "Checkpointer persistente" abaixo, é pré-requisito
- [ ] Rate limiting básico (por IP e/ou por usuário)

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
- [ ] Confirmar que `thread_id` (hoje `session_id` gerado por `uuid4()` em `interfaces/terminal/app.py`)
      continua sendo a chave certa quando existir usuário autenticado de verdade (via API)

**Verificado:** o grafo compila com o `MongoDBSaver` apontando pro db `frigus_ai` e as coleções
certas, e o `functools.cache` devolve a mesma instância entre chamadas. **Não verificado nesta
sessão:** gravar/recuperar estado contra um Mongo real (Docker não estava rodando no ambiente) —
rodar `python main.py terminal`, matar o processo e reabrir com o mesmo `session_id` pra confirmar
que o estado do grafo sobrevive, antes de dar merge.

## MCP e A2A

Requisito explícito da disciplina. `mcp_server/`, `a2a_server/` e `api/` foram **removidos do repo**
(eram só `__init__.py` vazio, sem implementação nenhuma — recriar quando o trabalho de cada um
começar de verdade, não versionar pasta placeholder sem uso).

- [ ] **MCP**: expor as tools do Frigus.AI (estoque, compras, receitas, financeiro, faq) como
      servidor MCP, pra hosts MCP externos (Claude Desktop etc.) conseguirem consumir o domínio do
      Frigus sem precisar do grafo inteiro
- [ ] **A2A**: expor `fluxo_agentes` (ou o módulo de serviço, pós-refactor) como agente
      Agent-to-Agent, pra outro sistema multiagente conseguir conversar com o Frigus.AI como um
      agente externo
- [ ] Decidir se os dois vivem só neste repo ou se algum consome a API (depende da decisão de
      localização da API acima)
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

Hoje não existe nenhuma instrumentação de tracing sobre o grafo — sem visibilidade de latência,
tokens ou erro por nó. Precisa cobrir, no mínimo, os 5 pontos do enunciado:

- [ ] **Tracing por nó** — avaliar LangSmith (mesmo caminho que o assessor-ai já percorreu: variáveis
      em `config/settings.py`, propagar pro `os.environ`, tags/metadata com `user_id`/`session_id`
      no `.invoke()`) ou alternativa gratuita equivalente, dado que a escola não paga API de LLM nem
      de observabilidade — confirmar tier gratuito antes de adotar
- [ ] **Latência interagentes e tempo total de resposta** — depende do tracing acima, ou logging
      manual de timestamp por nó (`config/logging.py`) se o tracing de terceiro não for viável
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

## Redis e Qdrant

`tools/redis/` e `tools/qdrant/` foram removidos do repo (eram só `__init__.py` vazio — recriar
quando a primeira tool de cada um existir de verdade). Não são requisito obrigatório da disciplina,
mas somam pra "complexidade do projeto" (item extra) e resolvem gaps reais:

- [ ] **Redis**: cache do perfil comportamental (`tools/mongo/users`, hoje sempre bate no Mongo) e/ou
      rate limit por usuário — mesmo padrão do assessor-ai (`tools/redis/{connection,perfil}.py`)
- [ ] **Qdrant**: mesmo caso de uso do assessor-ai (RAG de um único PDF via tool) — trocar o FAISS
      local em memória (`tools/faq_tools.py`, reconstrói o índice a cada start do processo) pelo
      padrão já validado lá: `tools/qdrant/faq/{connection,core,ingest}.py` (client lazy, tool
      `faq_retriever` fazendo `query_points`, script de ingestão separado da tool de busca). Baixo
      custo incremental (mais um serviço no `docker-compose.yml`, código já pronto de referência);
      o ganho real hoje é consistência com o assessor-ai, não performance — FAISS já é rápido pro
      tamanho atual do PDF. Eventualmente: busca semântica de receitas cruzando com o estoque
- [ ] **Em discussão:** remover o agente `faq` (`agents/nodes/faq.py` + `faq_app` em `graph/agents.py`)
      e deixar só a tool — o Roteador identifica que é pergunta de FAQ e chama `faq_retriever` direto,
      igual já acontece com `estoque`/`compras`/`financeiro` (nó chama a tool, `orquestrador` formata
      em linguagem natural, `juiz` valida). Não faz sentido pagar uma chamada de LLM extra só pra
      decidir usar a única tool que o agente FAQ tem — o Roteador já tomou essa decisão. Efeito
      colateral: reduz de 10 pros 9 nós no grafo (ainda bem acima do mínimo de 5 agentes exigido)
- [ ] Adicionar os dois serviços ao `docker-compose.yml` (hoje só tem `postgres`/`mongo`) quando a
      primeira tool de cada um existir — não subir infra sem uso

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
      quebrava na *coleção* sem `GEMINI_API_KEY`/`GROQ_API_KEY`/`DATABASE_URI`. Resolvido no
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
está implementado do que falta, e documenta as duas decisões em aberto: integração com o `assessor-ai` e
localização da API.

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
- [ ] **Neo4j** — não aparece em lugar nenhum do repo atual (nem README, nem estrutura de pastas). Se ainda é
      plano (auditoria de chamadas agente-a-agente via Cypher), está em estágio de ideia, não de placeholder.
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

**Resposta: mesmo repo.** Já existe uma pasta `api/` no repo do Frigus — então essa decisão já foi tomada
na prática, só falta confirmar se o conteúdo de lá está funcional. Motivos pra manter assim:

- Projeto acadêmico, escopo pequeno, provavelmente mantido por poucas pessoas
- API, grafo e tools compartilham o mesmo ciclo de vida e o mesmo deploy
- Separar repo cedo cria overhead de sincronizar versões, CI duplicado e dependências cruzadas sem
  nenhum ganho real nesse estágio

Só valeria separar se a API precisasse de deploy/versionamento independente do grafo, ou se times diferentes
fossem mexer em cada parte — nenhum dos dois parece ser o caso aqui.

- [ ] Verificar o que já existe dentro de `api/` (rotas, se usa FastAPI, se tá conectado ao grafo)

---

## Perguntas em aberto (preciso da sua resposta antes de codar)

1. O domínio Financeiro do assessor-ai vai **substituir** o MoneySaving atual, ou os dois vão coexistir
   (MoneySaving fica, e o assessor-ai cobre um financeiro pessoal mais amplo)?
2. Prioridade entre Redis (rate limit vs. cache vs. checkpointer) — qual entra primeiro?
3. Neo4j e LangSmith ainda estão no roadmap ou foram descartados nessa fase do projeto?
