"""
Logging do projeto. `setup.py` monta o logger (cor + request_id) e `decorators.py` loga as tools;
a classe `Logging` abaixo é só a fachada — `Logging.get_logger(__name__)` e `Logging.log_classe`
seguem sendo o ponto de entrada de todo o código.
"""

from frigus_ai.infra.logging.decorators import LogType, log_classe, log_tool
from frigus_ai.infra.logging.setup import DebugLevel, get_logger, request_id_var


class Logging:
    get_logger = staticmethod(get_logger)
    log_tool = staticmethod(log_tool)
    log_classe = staticmethod(log_classe)


__all__ = ["DebugLevel", "LogType", "Logging", "request_id_var"]
