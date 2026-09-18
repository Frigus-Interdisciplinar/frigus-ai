# Migração de tipos compartilhados

## Feito

- Fonte principal movida para `src/frigus_ai/types.py`.
- `services/types.py` permanece como fachada temporária.

## Falta fazer

- Atualizar imports restantes para `frigus_ai.types`.
- Remover `services/types.py` somente com autorização explícita.
- Verificar se todos os identificadores usados por API, services e tools têm tipos consistentes.
