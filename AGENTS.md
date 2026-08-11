# AGENTS.md

Contexto do projeto **Frigus.AI** para agentes de IA (Claude Code, Copilot, etc.) trabalhando neste
repositório.

## O que é

Assistente conversacional multi-agente do app **Frigus** (gestão de alimentos em geladeira/freezer/
despensa, compras, receitas e finanças domésticas). Construído com LangChain + LangGraph, RAG
(FAISS) e um agente juiz (LLM-as-judge) para mitigar alucinação. Também é o **projeto da disciplina
de Sistemas Multiagentes** — ver seção "Requisitos da disciplina" abaixo para o que precisa ser
entregue e o que já está feito.

`main.py` hoje concentra loop de terminal + montagem de estado + persistência (ver TODO.md — vai ser
quebrado numa camada de serviço compartilhada, no mesmo padrão do assessor-ai). Detalhes de
arquitetura, fluxo de agentes e tools estão no [README.md](README.md) — leia-o antes de mexer em
`agents/` ou `graph/`.

## Requisitos da disciplina

Baseado no enunciado do trabalho ("mínimo para 7,0" + extra). Cada item marca o que já está feito
neste repo e onde. Antes de reportar algo como pendente, confira o código — este checklist pode
ficar desatualizado.

| Requisito | Status | Onde |
|---|---|---|
| API FastAPI/Flask | ❌ Pendente | `api/` só tem `__init__.py`. **Decisão em aberto:** ver TODO.md — API fica neste repo ou vira repo separado |
| Multiagente, mínimo 5 agentes | ✅ Feito | 10 nós no grafo: guardrail entrada/saída, router, estoque, compras, receitas, faq, financeiro, orquestrador, juiz (`agents/nodes/names.py`) |
| LangChain para criação dos agentes | ✅ Feito | `graph/agents.py` |
| LangGraph para orquestração | ✅ Feito | `graph/builder.py` |
| Controle de sessões por usuário | ⚠️ Parcial | `thread_id=session_id` no checkpointer LangGraph (`main.py`) + histórico em Mongo (`tools/mongo/chats`), mas checkpointer é `MemorySaver` **em memória** — estado do grafo não sobrevive a restart. Sem API ainda, não existe sessão HTTP de fato |
| Memória de longo prazo | ⚠️ Parcial | `tools/mongo/users` — perfil comportamental (resumo de hábitos) por `user_id`, persistente no Mongo. Avaliar se cobre o requisito ou se precisa de algo além do resumo (ex. memória vetorial) |
| MCP, A2A (integrações com sistemas/agentes externos) | ❌ Pendente | `mcp_server/` e `a2a_server/` só têm `__init__.py` — ver TODO.md |
| RAG com fonte externa indicada | ✅ Feito | `tools/faq_tools.py` — FAISS sobre `data/Frigus-Documentacao.pdf` (fonte local, categoria explicitamente aceita pelo enunciado) |
| Agente juiz (mitigação de alucinação) | ✅ Feito | `agents/nodes/juiz.py` — audita grounding/relevância/completude, até 2 retentativas |
| Guardrail | ✅ Feito | `agents/nodes/guardrail/{entrada,saida}.py` |
| Observabilidade/SRE — custo estimado (100 e 1000 usuários/semana) | ❌ Pendente | ver TODO.md |
| Observabilidade/SRE — latência interagentes e tempo total de resposta | ❌ Pendente | sem tracing hoje (nem LangSmith nem logging estruturado de latência) |
| Observabilidade/SRE — índice de erros | ❌ Pendente | |
| Observabilidade/SRE — custo/ROI | ❌ Pendente | |
| Observabilidade/SRE — custo por resolução | ❌ Pendente | |
| Desenho de arquitetura de alto nível | ✅ Feito | README.md — diagrama Mermaid + `assets/diagrama-agentes.png` |
| Extra: complexidade do projeto | Em andamento | 5 domínios de negócio + guardrail duplo + juiz já é acima da média; MCP/A2A/observabilidade (pendentes acima) são o que mais soma aqui |

**Importante:** a escola não paga API de IA generativa — por isso o projeto já usa só providers com
tier gratuito viável (Gemini, Groq) e Claude/Anthropic como opcional (`ANTHROPIC_API_KEY` tem
default vazio em `config/settings.py`, então o projeto roda sem ela).

## Stack

- Python 3.13+, gerenciado com `uv` (`uv venv`, `uv sync`, `uv add <pkg>`)
- LangChain 1.2 / LangGraph 1.1 para orquestração de agentes
- LLMs: Gemini (`gemini-2.5-flash`), Groq (`llama-3.3-70b-versatile`, `qwen-2.5-pro`), Claude
  (`claude-haiku-4-5`, `claude-sonnet-4-6`) mapeados em `config/models.py`
- PostgreSQL (via Docker, auto start/stop em `config/docker.py`) para estoque/compras/receitas/
  financeiro, acessado via `psycopg2` cru (schema `dataload`, DDL fornecido em `data/sql/schema.sql`)
- MongoDB para histórico de conversa (`tools/mongo/chats`) e perfil comportamental
  (`tools/mongo/users`)
- FAISS para RAG do FAQ sobre `data/Frigus-Documentacao.pdf`
- Redis e Qdrant estão como pastas placeholder (`tools/redis/`, `tools/qdrant/`) — **nenhuma tool
  implementada ainda** (ver TODO.md)

## Estrutura

```
agents/     prompts (agents/prompts) e nós de grafo (agents/nodes) — um arquivo por agente/domínio
graph/      state.py (estado + Route), llm.py (builders), agents.py (agentes compilados), builder.py (grafo)
tools/      integrações externas: tools/postgres/{estoque,compras,receitas,financeiro}, tools/mongo/{chats,users}, faq_tools.py
config/     settings.py (env vars via pydantic-settings), models.py (Model enum + providers), docker.py, logging.py
ui/         terminal.py — Rich + pyfiglet (única interface hoje)
data/       Frigus-Documentacao.pdf (RAG) + sql/schema.sql (DDL fornecido)
api/        placeholder — não implementado (ver TODO.md)
mcp_server/ placeholder — não implementado (ver TODO.md)
a2a_server/ placeholder — não implementado (ver TODO.md)
```

Padrão de cada domínio de tool: `schemas.py` (Pydantic) + `core.py` (as tools em si), com
`connection.py`/`context.py`/`helpers.py` compartilhados em `tools/postgres/`. Siga esse padrão para
qualquer tool nova (redis, qdrant, etc).

## Convenções

- Código de domínio (nomes de função, variáveis, docstrings de tool, mensagens ao usuário) é em
  **português**; nomes de classes/tipos de infraestrutura (`Settings`, `Model`, `Route`) em inglês.
  Siga o idioma já usado no arquivo que você está editando.
- Enums de domínio usam `StrEnum` (ver `graph/state.py:Route`, `agents/nodes/names.py:NodeName`).
- Conexões com banco (Postgres, Mongo) são **lazy** — inicializadas só na primeira operação, nunca
  no import do módulo. Mantenha esse padrão para novas integrações (Redis, Qdrant, MCP, A2A).
- Tools retornam a classe `Response` (`tools/response.py`) para padronizar sucesso/erro.
- **Tools do LLM nunca recebem `user_id`/`stock_id` como argumento.** Args de tool são escolhidos
  pelo LLM via tool-calling — qualquer dado de escopo/permissão não pode vir por ali. O padrão é um
  `contextvars.ContextVar` setado uma vez por request (`tools/postgres/context.py:session_context`,
  chamado em `main.py:executar_fluxo_frigus`) e lido dentro da tool. Ver uso em
  `tools/postgres/{estoque,compras,receitas,financeiro}/core.py`.
- Não commitar `.env`; usar `.env.example` como referência de variáveis novas.
- **Simplicidade acima de tudo.** Projeto de disciplina em estágio inicial — prefira a solução direta
  à abstração "flexível para o futuro". Sem camada genérica, sem config plugável, sem interface para
  uma única implementação. Isso vale tanto para código de domínio quanto para infra.

## Fluxo de trabalho (Git)

- Mudança de qualquer tamanho (feature, fix, refactor) vai em **branch própria**, nunca commit
  direto em `main` — exceção só pra coisas triviais tipo ajuste de README/badge.
- Nome de branch segue `tipo/slug-curto`, mesmo padrão já usado no repo (`feat/big-bang`,
  `feat/chatbot-multiagentes`, `docs/melhorias-readme`). Tipos comuns: `feat`, `fix`, `refactor`,
  `docs`, `chore`.
- Commits seguem o padrão `tipo: descrição curta` (`feat:`, `fix:`, `docs:`, `chore:`) — ver
  `git log` para exemplos reais.
- Mudança termina em **Pull Request** para `main` — mantém o histórico navegável e dá um ponto de
  review antes do merge.

## Padrões de organização e clean code

- **Single responsibility por nó de agente.** `agents/nodes/` (execução) fica separado de
  `agents/prompts/` (conteúdo/persona) — mudar o texto de um prompt nunca deveria exigir tocar na
  lógica de roteamento do grafo, e vice-versa.
- **Contrato de retorno único.** Tools não retornam dict cru nem deixam exception vazar para o
  agente — usam `Response` (`tools/response.py`). Ao criar tool nova, reusar essa classe.
- **Config centralizada.** Uma única fonte de env vars (`config/settings.py`, `pydantic-settings`) e
  um único enum fechado de modelos/providers (`config/models.py:Model`/`PROVIDER_MAP`). Não ler
  `os.environ` direto em outros módulos.
- **Ciclo de retentativa do Juiz é explícito no grafo**, não escondido em loop Python — ver
  `decidir_apos_juiz` em `graph/builder.py`. Qualquer novo especialista que produza resposta ao
  usuário deve passar pelo Juiz antes do Guardrail de Saída, seguindo esse mesmo padrão de edge
  condicional.

## Comandos

```bash
uv venv && uv sync   # instalar dependências
python main.py       # rodar o assistente no terminal (sobe Postgres/Mongo via Docker automaticamente)
```

Não há suíte de testes no projeto ainda (ver TODO.md).

## Ao adicionar uma tool nova

1. Criar `tools/<sistema>/<domínio>/schemas.py` com os modelos Pydantic de entrada/saída.
2. Criar `tools/<sistema>/<domínio>/core.py` com as funções decoradas como tool (ver
   `config/decorators.py:log_tool`).
3. Se for um serviço externo com estado de conexão, criar `connection.py` com init lazy.
4. Se a tool precisa ser escopada por usuário/estoque, usar o `ContextVar` de
   `tools/postgres/context.py` — nunca adicionar `user_id`/`stock_id` ao schema da tool.
5. Registrar a tool no agente correspondente em `agents/nodes/`.
6. Atualizar a tabela de estrutura no README.md.

## Próximos passos

Refatoração de estrutura e roadmap de implementação (MCP, A2A, observabilidade, etc.) estão em
[TODO.md](TODO.md) — confira antes de começar qualquer trabalho novo, pra não duplicar decisão já
tomada ou já descartada lá.

## Claude Code

Para instruções específicas de como o Claude Code deve operar neste repo, ver [CLAUDE.md](CLAUDE.md).
