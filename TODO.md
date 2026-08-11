# TODO

Próximos passos planejados. Contexto do projeto e checklist de requisitos da disciplina em
[AGENTS.md](AGENTS.md).

## Refatoração de estrutura — alinhar com o assessor-ai

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

- [ ] Criar `src/frigus_ai/` e mover `agents/`, `graph/`, `tools/` pra dentro (ajustar imports:
      `graph.builder` → `frigus_ai.graph.builder`, etc.) — confirmar se o pacote fica instalável via
      `hatchling` (`[tool.hatch.build.targets.wheel] packages = ["config", "interfaces",
      "src/frigus_ai"]`, mesmo bloco do assessor-ai) ou se `pip install -e .`/`uv sync` já resolve
      sem esse passo extra
- [ ] Extrair `executar_fluxo_frigus`, `montar_mensagem_humana`, `salvar_mensagens`,
      `_extrair_resposta` de `main.py` para `src/frigus_ai/chat/` (ou nome equivalente)
- [ ] `main.py` vira dispatcher fino (hoje só tem uma interface — terminal — mas deixa o gancho
      pronto pra quando a API existir, seguindo o padrão `python main.py <interface>` do assessor-ai)
- [ ] `ui/terminal.py` migra para `interfaces/terminal/` (ou equivalente), sem lógica de negócio,
      fora de `src/`
- [ ] Nenhuma interface deve chamar `frigus_ai.graph.builder`, `frigus_ai.tools.mongo.*` ou
      `frigus_ai.tools.postgres.*` diretamente — sempre via o módulo de serviço. É esse limite que
      permite a API existir sem duplicar a lógica de montar estado, invocar o grafo e persistir
      histórico

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

## Checkpointer persistente (controle de sessão)

`graph/builder.py` usa `MemorySaver` — estado do LangGraph some a cada restart do processo. Pra
"controle de sessões por usuário" valer de verdade (requisito da disciplina) e pra sessão sobreviver
a redeploy da API, trocar por um checkpointer persistente.

- [ ] Avaliar `MongoDBSaver` (`langgraph-checkpoint-mongodb`) — já tem Mongo no projeto, evita
      adicionar infra nova. Ver achado do assessor-ai sobre pin de versão do `pymongo` incompatível
      com a lib antes de instalar
- [ ] Confirmar que `thread_id` (hoje `session_id` gerado por `uuid4()` em `main.py`) continua sendo
      a chave certa quando existir usuário autenticado de verdade (via API)

## MCP e A2A

Requisito explícito da disciplina. `mcp_server/` e `a2a_server/` só têm `__init__.py` hoje.

- [ ] **MCP**: expor as tools do Frigus.AI (estoque, compras, receitas, financeiro, faq) como
      servidor MCP, pra hosts MCP externos (Claude Desktop etc.) conseguirem consumir o domínio do
      Frigus sem precisar do grafo inteiro
- [ ] **A2A**: expor `fluxo_agentes` (ou o módulo de serviço, pós-refactor) como agente
      Agent-to-Agent, pra outro sistema multiagente conseguir conversar com o Frigus.AI como um
      agente externo
- [ ] Decidir se os dois vivem só neste repo ou se algum consome a API (depende da decisão de
      localização da API acima)

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

## Redis e Qdrant — placeholders sem tool nenhuma

`tools/redis/` e `tools/qdrant/` só têm `__init__.py`. Não são requisito obrigatório da disciplina,
mas somam pra "complexidade do projeto" (item extra) e resolvem gaps reais:

- [ ] **Redis**: cache do perfil comportamental (`tools/mongo/users`, hoje sempre bate no Mongo) e/ou
      rate limit por usuário — mesmo padrão do assessor-ai (`tools/redis/{connection,perfil}.py`)
- [ ] **Qdrant**: RAG do FAQ com banco vetorial de verdade em vez do FAISS local em memória, e
      eventualmente busca semântica de receitas cruzando com o estoque do usuário
- [ ] Adicionar os dois serviços ao `docker-compose.yml` (hoje só tem `postgres`/`mongo`) quando a
      primeira tool de cada um existir — não subir infra sem uso

## Testes

Não existe suíte de testes no projeto. Seguir o ponto de partida do assessor-ai: começar pelas
funções puras, sem precisar mockar banco.

- [ ] `pytest` como dev dependency (`uv add --dev pytest`)
- [ ] `tests/tools/` — `Response.ok`/`Response.error` (`tools/response.py`), helpers de
      `tools/postgres/helpers.py` (`normalize_enum`, cálculo de semáforo de validade, `next_id`) que
      não dependem de conexão real
- [ ] Depois: `tests/agents/nodes/guardrail/` (bloqueio determinístico por regex, sem chamar LLM)
- [ ] CI (GitHub Actions) rodando `ruff check .` + `pytest` — repo já tem `.github/`, confirmar se
      workflow existe antes de recriar
