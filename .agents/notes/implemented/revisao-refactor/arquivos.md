# Revisão do refactor

## Concluído

- MCP consolidado em `src/frigus_ai/mcp.py`; `api/routes/mcp.py` ficou como adaptador.
- Teste MCP atualizado para importar o módulo único.
- O mapa/lock A2A foi substituído por Redis compartilhado com `SET NX EX` e TTL.
- `/health/ready` passou a testar cada dependência separadamente.
- `AGENTS.md` recebeu o checklist por matéria/entrega.

## Limites conhecidos

- A associação `context_id -> user_id` agora é compartilhada no Redis; a integração SDK alternativa
  ainda usa usuário padrão e o histórico completo continua no Mongo/checkpointer.
- A2A manual e A2A SDK continuam coexistindo até a decisão de contrato.
- Prometheus/Grafana estão configurados, mas dependem do Docker daemon e de `.env` completo
  para validação real.
