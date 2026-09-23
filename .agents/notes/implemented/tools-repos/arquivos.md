# Migração ToolSet para Repo

> **Nota atualizada e arquivada em 2026-09-23.** O item que faltava — migrar `compras` — foi
> feito (`repositories/compras_repository.py`, SQLAlchemy + `@transacional`; ver
> `pending/requisitos-disciplina/arquivos.md`). `receitas`/`financeiro`/`estoque`/`compras`
> estão todos migrados; SQL cru sumiu do projeto. Os arquivos `*/toolset.py` continuam no repo
> como alias de compatibilidade (`ComprasToolSet = ComprasRepo` etc.) — hoje só `faq` e
> `spoonacular` ainda têm teste (`test_toolset.py`) contra o nome antigo; `compras`/`estoque`/
> `financeiro`/`receitas` não têm import nenhum fora do próprio arquivo, candidatos a remoção
> numa sessão futura, com autorização explícita (`CLAUDE.md`).

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

- ~~Migrar `compras`~~ — feito: `repositories/compras_repository.py`, mesmo padrão de
  `receitas`/`financeiro`/`estoque` (SQLAlchemy + `@transacional`). Pool `psycopg2` cru
  removido do projeto.
- Remover `*/toolset.py` de `compras`/`estoque`/`financeiro`/`receitas` (sem import fora do
  próprio arquivo hoje). `faq`/`spoonacular` ainda têm teste contra o nome antigo — mexer
  neles primeiro ou junto. Só com autorização explícita (`CLAUDE.md`).
- Revisar models SQLAlchemy por domínio sem copiar IDs/tabelas do assessor cegamente.

## Arquivos

`src/frigus_ai/graph/tools/`, `src/frigus_ai/infra/postgres/`,
`src/frigus_ai/repositories/{financeiro,estoque}_repository.py`,
`tests/tools/`, `tests/repositories/test_{financeiro,estoque}_repository.py`.
