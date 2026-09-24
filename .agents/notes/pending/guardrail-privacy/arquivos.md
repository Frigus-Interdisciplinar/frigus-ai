# Guardrail: organização + custo

## Feito

- `frigus_ai/privacy.py` criado (espelha `assessor_ai/privacy.py`): PII, `anonimizar_entrada`,
  `desanonimizar_saida`, `redigir_pii`, `MapaPII`. Antes isso morava em
  `graph/nodes/guardrail/entrada.py` (hoje `graph/guardrail/`) e `chat_repository`/`user_service` importavam de lá —
  persistência e serviço dependendo de um nó de LangGraph. Inversão resolvida.
- `guardrail/` saiu de `graph/nodes/` para `graph/guardrail/` — virou subsistema próprio,
  com os nós sendo só a porta de entrada dele — e foi dividido por natureza: `padroes.py` (detecção de ataque, regex
  compilado no import), `schemas.py` (tipos + política), `cache.py` (Redis), `entrada.py`/
  `saida.py` (só os nós).
- `RESPOSTAS_BLOQUEIO` virou `dict[Categoria, RespostaBloqueio]` (TypedDict) no lugar de
  tupla, e `Motivo` virou `Literal` — o motivo é label do Prometheus, então typo viraria
  série nova de métrica.
- Cache do classificador no Redis: a chave carrega o fingerprint do prompt (editar
  `guardrail.md` invalida sozinho) e os tokens de PII são normalizados antes do hash, senão
  mensagem com PII nunca bateria (o token tem sufixo aleatório).
- `infra/redis/connection.py` ganhou `socket_connect_timeout`/`socket_timeout` de 0.5s:
  o default do redis-py esperava ~4s POR chamada com o Redis fora do ar (medido).
  `cache.py` ainda se desliga por 30s depois de uma falha, pra cache fora do ar nunca
  deixar o turno mais lento que sem cache.
- Lookup de categoria é por `str` crua, não `Categoria(...)`: converter estourava
  ValueError se o LLM inventasse categoria fora da lista, derrubando o turno em vez de
  cair na falha aberta. Tem teste.

- Classificador de entrada com `with_structured_output(Classificacao)` (schema com `Categoria`)
  no lugar do parsing de `CATEGORIA:`. Falha aberta só em erro real (chamada ou schema), e
  essa falha não vai pro cache.
- Guardrail de saída só chama o LLM quando `precisa_revisao` acha termo de risco (segurança
  alimentar, saúde/nutrição, certeza de validade); resposta limpa sai sem LLM.

## Falta fazer

- Avaliar limiar pra pular o classificador em mensagens curtas e óbvias do domínio (sem
  perder cobertura de jailbreak, que é regex e roda sempre).

## Arquivos

`src/frigus_ai/privacy.py`, `src/frigus_ai/graph/guardrail/`,
`src/frigus_ai/infra/redis/{connection,keys}.py`,
`tests/graph/guardrail/`.
