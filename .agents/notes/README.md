# Handoff: continuidade do Frigus.AI

## Como continuar em outra sessão

1. Ler este arquivo inteiro antes de alterar qualquer coisa.
2. Ler `AGENTS.md` e respeitar a regra: **não alterar nem apagar código sem solicitação explícita**.
3. Ler primeiro as notas pendentes em `pending/`, especialmente:
   - `pending/requisitos-disciplina/arquivos.md` — **começa por aqui**: placar dos requisitos
     e ordem P0/P1/P2 do que ainda falta pra nota
   - `pending/neo4j/arquivos.md` — sync Postgres→Neo4j e mapeamento fatos→relações
   - `pending/visao/arquivos.md` — limpeza de checkpoint, retry do Juiz, fallback de provider
   - `pending/api-e-services/arquivos.md` — schemas de resposta e organização de rotas
   - `pending/guardrail-privacy/arquivos.md` — custo do guardrail de saída
   - `pending/jev/arquivos.md` — onde o JeV já decide e os próximos usos (guardrail de saída,
     categoria e resolução de nome de produto)
   - `observability/RELATORIO.md` — cenários, SRE e sessões rodados contra a infra real
4. Consultar `implemented/` só para entender decisões já tomadas
   (`contratos-grafo-e-repositories`, `memoria-fatos`). Notas obsoletas foram apagadas; o histórico
   está no git.
5. Conferir `git status --short --branch` antes de editar.

## Não repetir

- Não reintroduzir `{"role": ...}` nos nós; usar `HumanMessage`/`AIMessage`/`SystemMessage`.
- Não voltar `names.py` nem PII pra dentro de `nodes/` — os dois saíram por causa de ciclo de
  import e de inversão de dependência reais, não por estética.
- Não checar ownership no corpo de rota que é gerador (SSE): tem que ser dependência, senão
  roda depois que o status HTTP já saiu.
- Não reviver a integração A2A via `a2a-sdk` sem o card anunciar
  streaming/tasks de verdade — hoje é operação única, o contrato manual já cobre.
- Não apagar arquivos sem permissão prévia explícita do usuário.
- Não commitar `.env` nem expor credenciais.

## Restrições importantes

- Não restaurar ou reverter arquivos marcados como deletados no `git status` sem entender por
  quê primeiro — podem ser parte de uma decisão já tomada nesta sessão ou numa anterior.
- Não considerar um requisito "pronto" só porque a rota responde 200 — ler o `Placar` de
  `pending/requisitos-disciplina/arquivos.md` pra saber o que já foi validado contra infra real
  e o que só passou com mock.
