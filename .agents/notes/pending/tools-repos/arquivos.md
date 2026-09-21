# Migração ToolSet para Repo

## Feito

- Implementações principais foram movidas para `repo.py`.
- Classes passaram a se chamar `*Repo`.
- Registro central usa `*_repo`.
- `financeiro` migrado do psycopg2 cru para SQLAlchemy + `@transacional`
  (`repositories/financeiro_repository.py`), mesmo desenho de `receitas`: o repository faz
  só persistência e a tool (`graph/tools/financeiro/repo.py`) fica com `Response`, log e
  aritmética de mês/variação. Sumiram 4 blocos de `with get_conn()/cursor/try/except`.
  `gastos_por_mes` agora resolve N meses numa query só (antes era uma por mês) e preenche
  com `0.0` o mês sem movimento, que antes sumia do resultado.
  Escolhido como primeiro por ser somente leitura — não tinha `commit`/`rollback` a preservar.
- `estoque` migrado na sequência (`repositories/estoque_repository.py`), o primeiro com
  escrita: cada método público é uma unidade de trabalho inteira sob `@transacional`, com
  localizar + alterar na MESMA transação (separar abriria janela entre ler a quantidade e
  gravar a nova). Sumiram 4 blocos de `get_conn`/`commit`/`rollback`. O upsert
  `ON CONFLICT (product_id, stock_id, expire_date) DO UPDATE` virou
  `insert(...).on_conflict_do_update(...)` do dialeto Postgres, com SQL conferido.
  Regras de negócio viraram exceptions de domínio (`ItemDeEstoqueNaoEncontrado`,
  `QuantidadeNegativa`) pra tool traduzir em `Response.error` preservando a mensagem.
  `_localizar` agora prende o `stock_id` também no caminho por ID — antes um ID de outro
  estoque era alcançável.
  **Cuidado ao mexer:** `descartar()` grava a saída em `stock_movements` com a MESMA data
  do `discard`; é por (stock_product_id, date) que o financeiro casa os dois pra calcular
  desperdício. Há teste cravando isso.

## Falta fazer

- Migrar `compras`, o último domínio Postgres em SQL cru, para `PostgresRepo`/SQLAlchemy.
  `receitas`, `financeiro` e `estoque` já estão migrados.
- Garantir `Response`, escopo por `session_context` e `as_tools()` em todos os domínios.
- Remover imports de `toolset.py` após atualizar testes e chamadores.
- Apagar fachadas `toolset.py` somente com autorização explícita.
- Revisar models SQLAlchemy por domínio sem copiar IDs/tabelas do assessor cegamente.

## Arquivos

`src/frigus_ai/graph/tools/`, `src/frigus_ai/infra/postgres/`,
`src/frigus_ai/repositories/{financeiro,estoque}_repository.py`,
`tests/tools/`, `tests/repositories/test_{financeiro,estoque}_repository.py`.
