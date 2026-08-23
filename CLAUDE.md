# CLAUDE.md

Contexto completo do projeto, requisitos da disciplina, arquitetura e convenções está em
[AGENTS.md](AGENTS.md) — leia-o primeiro. Este arquivo só existe para instruções específicas do
Claude Code; não duplique conteúdo do AGENTS.md aqui.

## Instruções específicas para o Claude Code

- Este é um projeto de disciplina em estágio inicial — prefira mudanças diretas e simples, sem
  abstrações especulativas. Ver checklist de "Requisitos da disciplina" no AGENTS.md antes de propor
  trabalho novo — priorize o que ainda está ❌/⚠️ lá.
- Respeite o idioma do arquivo (português para código de domínio, inglês para infraestrutura) — ver
  seção "Convenções" do AGENTS.md.
- Antes de adicionar uma tool nova (Redis, Qdrant, MCP, A2A, API, etc.), siga o padrão descrito em
  "Ao adicionar uma tool nova" no AGENTS.md e confira o [TODO.md](TODO.md) para o que já está
  planejado ou decidido.
- Antes de escrever código novo que toque FastAPI, Pydantic, MongoDB/pymongo, LangChain/LangGraph ou
  o client do Spoonacular, confira `.agents/skills/<lib>.md` — são pegadinhas reais já encontradas
  neste repo ou no assessor-ai (ver seção "Skills por biblioteca" do AGENTS.md).
- **API (FastAPI/Flask) fica neste mesmo repositório** — decidido, sem repo separado. Ver
  "Decisão: API no mesmo repo ou separado?" no TODO.md.
- Não rodar `docker stop`/`docker start` fora do fluxo de `config/docker.py` sem avisar o usuário —
  os containers Postgres/Mongo podem estar compartilhados com outras execuções locais.
