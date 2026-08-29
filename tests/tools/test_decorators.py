"""
Regressão de vazamento em log: `log_tool` logava args e result inteiros das tools —
ou seja, alimentos, gastos e nomes do usuário em texto puro no log local.
"""

from config.decorators import log_tool


@log_tool
def _tool_fake(produto: str) -> dict:
    return {"status": "ok", "itens": [produto]}


@log_tool
def _tool_que_falha(produto: str) -> dict:
    return {"status": "error", "erro": produto}


def test_log_nao_inclui_argumentos_nem_resultado(caplog):
    with caplog.at_level("INFO"):
        _tool_fake("leite integral")

    assert "leite integral" not in caplog.text
    assert "_tool_fake" in caplog.text


def test_log_de_erro_tambem_nao_inclui_resultado(caplog):
    with caplog.at_level("INFO"):
        _tool_que_falha("leite integral")

    assert "leite integral" not in caplog.text
    assert "ERRO" in caplog.text


def test_decorator_devolve_o_resultado_intacto():
    assert _tool_fake("leite") == {"status": "ok", "itens": ["leite"]}
