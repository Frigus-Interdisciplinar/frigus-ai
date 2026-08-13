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
