from datetime import date, timedelta

# Rótulos em português dos enums (o banco grava o código em inglês), usados aqui pra normalizar
# entradas em linguagem natural do LLM (ex.: "geladeira" -> "Geladeira"). Fonte única em
# infra/postgres/models/estoque.py — não duplicar a lista aqui.
from frigus_ai.infra.postgres.models.estoque import (
    CATEGORY_VALUES,
    PRODUCT_STATUS_VALUES,
    STORAGE_PLACE_VALUES,
)

# Limiares do semáforo de validade (dias até expire_date)
DIAS_ATENCAO = 7   # amarelo
DIAS_CRITICO = 2   # vermelho


def normalize_enum(value: str | None, allowed: list[str]) -> str | None:
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


def compute_product_status(expire_date: date, hoje: date | None = None) -> str:
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


def expiring_date_threshold(dias: int = DIAS_ATENCAO) -> date:
    return date.today() + timedelta(days=dias)


__all__ = [
    "CATEGORY_VALUES",
    "DIAS_ATENCAO",
    "DIAS_CRITICO",
    "PRODUCT_STATUS_VALUES",
    "STORAGE_PLACE_VALUES",
    "compute_product_status",
    "expiring_date_threshold",
    "normalize_enum",
]
