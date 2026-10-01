"""Logger colorido, com o `request_id` da API injetado em cada linha."""

import logging
from contextvars import ContextVar
from enum import StrEnum

# Setado pelo middleware da API a cada request; vazio fora dela (TUI, scripts).
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class Colors(StrEnum):
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    WHITE  = "\033[97m"
    RESET  = "\033[0m"


class DebugLevel(StrEnum):
    DEBUG    = "DEBUG"
    INFO     = "INFO"
    WARNING  = "WARNING"
    ERROR    = "ERROR"
    CRITICAL = "CRITICAL"


LEVEL_COLORS: dict[str, Colors] = {
    DebugLevel.DEBUG.value:    Colors.WHITE,
    DebugLevel.INFO.value:     Colors.GREEN,
    DebugLevel.WARNING.value:  Colors.YELLOW,
    DebugLevel.ERROR.value:    Colors.RED,
    DebugLevel.CRITICAL.value: Colors.RED,
}


class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = LEVEL_COLORS.get(record.levelname, Colors.WHITE)
        return f"{color}{super().format(record)}{Colors.RESET}"


def _injetar_request_id(record: logging.LogRecord) -> bool:
    rid = request_id_var.get()
    record.request_id = f"[{rid}] " if rid else ""
    return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(_injetar_request_id)
        handler.setFormatter(_ColorFormatter("%(levelname)s | %(name)s | %(request_id)s%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    return logger


__all__ = ["Colors", "DebugLevel", "get_logger", "request_id_var"]
