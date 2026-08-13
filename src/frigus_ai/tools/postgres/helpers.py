from datetime import date, timedelta
from typing import Optional

# Valores exatos dos enums do schema (data/sql/schema.sql) — usados para
# normalizar entradas em linguagem natural do LLM (ex.: "geladeira" -> "Geladeira").
CATEGORY_VALUES = [
    "Fruta", "Verdura", "Laticínio", "Carne", "Grão",
    "Bebida", "Limpeza", "Higiene Pessoal",
]

STORAGE_PLACE_VALUES = ["Geladeira", "Freezer", "Despensa", "Armário", "Prateleira"]

PRODUCT_STATUS_VALUES = ["Fresco", "Próximo do vencimento", "Vencido"]

# Limiares do semáforo de validade (dias até expire_date)
DIAS_ATENCAO = 7   # amarelo
DIAS_CRITICO = 2   # vermelho


def normalize_enum(value: Optional[str], allowed: list[str]) -> Optional[str]:
    """
    Resolve um valor livre (ex.: vindo do LLM) para o valor exato do enum,
    comparando sem acento/case. Retorna None se não encontrar correspondência.
    """

    if not value:
        return None

    def _sem_acento(s: str) -> str:
        troca = str.maketrans("áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ", "aaaaeeiooouucAAAAEEIOOOUUC")
        return s.translate(troca).strip().lower()

    alvo = _sem_acento(value)
    for opcao in allowed:
        if _sem_acento(opcao) == alvo:
            return opcao

    return None


def compute_product_status(expire_date: date, hoje: Optional[date] = None) -> str:
    """
    Calcula o semáforo (Fresco | Próximo do vencimento | Vencido) a partir da
    data de validade, com os mesmos limiares usados nas queries de estoque.
    """

    hoje = hoje or date.today()
    dias_restantes = (expire_date - hoje).days

    if dias_restantes < 0:
        return "Vencido"
    if dias_restantes <= DIAS_ATENCAO:
        return "Próximo do vencimento"
    return "Fresco"


def resolve_stock_id(cur, user_id: int) -> Optional[int]:
    """
    Resolve o stock_id do usuário: users -> user_groups -> groups -> stocks.
    Se o usuário pertencer a mais de um grupo, usa o primeiro vínculo (ORDER BY user_groups.id).
    """

    cur.execute(
        """
        SELECT s.id
        FROM user_groups ug
        JOIN stocks s ON s.group_id = ug.group_id
        WHERE ug.user_id = %s
        ORDER BY ug.id ASC
        LIMIT 1;
        """,
        (user_id,)
    )
    row = cur.fetchone()
    return row[0] if row else None


def expiring_date_threshold(dias: int = DIAS_ATENCAO) -> date:
    return date.today() + timedelta(days=dias)


def next_id(cur, table: str) -> int:
    """
    A maioria das tabelas do schema `dataload` usa INTEGER PRIMARY KEY sem
    SERIAL/IDENTITY (o DDL foi pensado para carga de dados, não para inserts
    incrementais de app). Para inserts vindos do chatbot, geramos o próximo ID
    disponível na hora. Não é seguro contra concorrência pesada, mas é
    suficiente para o escopo deste assistente.
    """

    cur.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table};")
    return cur.fetchone()[0]


__all__ = [
    "CATEGORY_VALUES",
    "STORAGE_PLACE_VALUES",
    "PRODUCT_STATUS_VALUES",
    "DIAS_ATENCAO",
    "DIAS_CRITICO",
    "normalize_enum",
    "compute_product_status",
    "resolve_stock_id",
    "expiring_date_threshold",
    "next_id",
]
