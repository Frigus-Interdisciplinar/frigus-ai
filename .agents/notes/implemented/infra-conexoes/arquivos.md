# Migração de infraestrutura

## Feito

- Postgres, Mongo, Redis e Qdrant possuem classes de conexão lazy.
- Fachadas antigas de acesso foram preservadas durante a migração.

## Falta fazer

- Implementar/avaliar `MongoRepo` genérico.
- Revisar dispose/close no lifespan.
- Health checks agora são separados por dependência em `/health/ready`; falta validar com a stack real.
- Confirmar a separação entre pool síncrono das tools e pool async do checkpointer.
- Cobrir lazy initialization e ciclo de vida com testes.

## Arquivos

`src/frigus_ai/infra/`, `src/frigus_ai/api/lifespan.py`,
`src/frigus_ai/api/routes/health.py`.
