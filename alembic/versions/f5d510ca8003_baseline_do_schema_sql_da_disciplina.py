"""baseline do schema.sql da disciplina

Revision ID: f5d510ca8003
Revises:
Create Date: 2026-09-17 00:00:00.000000

Marco zero das migrations — não recria nada do zero, só registra o schema
`dataload` já fornecido pela disciplina (`data/sql/schema.sql`) como ponto de
partida do Alembic.

Num banco que JÁ tem o schema `dataload` aplicado (o caso normal de dev/CI que
recebeu o dump da disciplina): rode `alembic stamp f5d510ca8003` em vez de
`upgrade` — stamp só grava a revisão, sem tentar recriar tabelas que já existem.

Só rode `upgrade` de verdade num banco vazio (ex.: ambiente novo sem o dump).
"""

from pathlib import Path

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f5d510ca8003"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA_SQL = Path(__file__).resolve().parents[2] / "data" / "sql" / "schema.sql"


def _corpo_sem_transacao() -> str:
    """
    `data/sql/schema.sql` já embrulha em BEGIN/COMMIT (pensado pra rodar via
    psql direto) — o Alembic gerencia a própria transação, então essas duas
    linhas saem daqui pra não aninhar transação.
    """

    linhas = _SCHEMA_SQL.read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in linhas if l.strip() not in ("BEGIN;", "COMMIT;"))


def upgrade() -> None:
    op.execute(sa.text(_corpo_sem_transacao()))


def downgrade() -> None:
    op.execute(sa.text("DROP SCHEMA IF EXISTS dataload CASCADE;"))
