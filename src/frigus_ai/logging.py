import functools
import inspect
import logging
import time
from enum import StrEnum


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


class Logging:
    """Setup de logger colorido + decorators de log das tools, tudo num lugar só."""

    @classmethod
    def _color_formatter(cls, fmt: str) -> logging.Formatter:
        class ColorFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                color = LEVEL_COLORS.get(record.levelname, Colors.WHITE)
                return f"{color}{super().format(record)}{Colors.RESET}"

        return ColorFormatter(fmt)

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        logger = logging.getLogger(name)

        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(cls._color_formatter("%(levelname)s | %(name)s | %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)

        return logger

    @staticmethod
    def log_tool(func=None, *, level: DebugLevel = DebugLevel.INFO):
        """Loga chamada/resultado de uma tool. Usável como `@log_tool` ou
        `@log_tool(level=DebugLevel.DEBUG)` pra baixar o nível das mensagens de rotina
        (erro sempre sai em ERROR, independente do `level`)."""

        def decorator(func):
            logger = Logging.get_logger("pg_tools")
            log_rotina = getattr(logger, DebugLevel(level).value.lower())

            def registrar_resultado(result, elapsed):
                status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
                if status == "error":
                    logger.error("ERRO     | %s | elapsed=%.3fs", func.__name__, elapsed)
                else:
                    log_rotina("OK       | %s | elapsed=%.3fs", func.__name__, elapsed)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                log_rotina("CHAMANDO | %s", func.__name__)

                start = time.perf_counter()
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                registrar_resultado(result, elapsed)
                return result

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                log_rotina("CHAMANDO | %s", func.__name__)

                start = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                registrar_resultado(result, elapsed)
                return result

            return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

        return decorator(func) if func is not None else decorator

    @staticmethod
    def log_classe(cls_alvo=None, *, level: DebugLevel = DebugLevel.INFO):
        """Aplica `log_tool` em todo método público da classe. Usável como
        `@log_classe` ou `@log_classe(level=DebugLevel.DEBUG)`."""

        def decorator(cls_alvo):
            for nome, atributo in list(vars(cls_alvo).items()):
                if nome.startswith("_") or not inspect.isfunction(atributo):
                    continue
                setattr(cls_alvo, nome, Logging.log_tool(atributo, level=level))
            return cls_alvo

        return decorator(cls_alvo) if cls_alvo is not None else decorator


__all__ = ["DebugLevel", "Logging"]
