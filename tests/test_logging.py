import logging

from frigus_ai.infra.logging import DebugLevel, Logging, request_id_var
from frigus_ai.infra.logging.decorators import LogType, _tipo_do_metodo, log_tool


def test_tipo_do_metodo_vem_do_prefixo():
    assert _tipo_do_metodo("buscar_fatos") is LogType.QUERY
    assert _tipo_do_metodo("descartar_item") is LogType.DELETE
    assert _tipo_do_metodo("qualquer_coisa") is LogType.TOOL


def test_logger_injeta_request_id_quando_setado(caplog):
    logger = Logging.get_logger("teste.request_id")
    registros = []

    class _Captura(logging.Handler):
        def emit(self, record):
            registros.append(record)

    captura = _Captura()
    captura.addFilter(logger.handlers[0].filters[0])
    logger.addHandler(captura)

    token = request_id_var.set("abc-1")
    try:
        logger.info("oi")
    finally:
        request_id_var.reset(token)
    logger.info("sem id")

    assert [r.request_id for r in registros] == ["[abc-1] ", ""]


def test_log_tool_preserva_resultado_e_nome():
    @log_tool(level=DebugLevel.DEBUG)
    def buscar_algo():
        return {"status": "ok"}

    assert buscar_algo() == {"status": "ok"}
    assert buscar_algo.__name__ == "buscar_algo"


def test_fachada_expoe_as_mesmas_funcoes_dos_submodulos():
    from frigus_ai.infra.logging.decorators import log_classe
    from frigus_ai.infra.logging.setup import get_logger

    assert Logging.get_logger is get_logger
    assert Logging.log_tool is log_tool
    assert Logging.log_classe is log_classe
