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
