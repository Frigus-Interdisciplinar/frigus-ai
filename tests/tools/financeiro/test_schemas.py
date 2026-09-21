"""
Guardas dos args que o LLM preenche: a validação virou responsabilidade do
Pydantic (antes só o prompt e o corpo da função sabiam dessas regras).
"""

import pytest
from pydantic import ValidationError

from frigus_ai.graph.tools.financeiro.schemas import EvolucaoDesperdicioArgs, MesArgs


def test_mes_precisa_ser_yyyy_mm():
    assert MesArgs(mes="2026-08").mes == "2026-08"
    assert MesArgs().mes is None

    for invalido in ("agosto", "2026-13", "26-08", "2026-8"):
        with pytest.raises(ValidationError):
            MesArgs(mes=invalido)


def test_evolucao_desperdicio_exige_meses_positivo():
    assert EvolucaoDesperdicioArgs().meses == 6

    with pytest.raises(ValidationError):
        EvolucaoDesperdicioArgs(meses=0)
