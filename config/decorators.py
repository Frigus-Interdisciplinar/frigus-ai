import functools
import time

from config.logging import get_logger

logger = get_logger("pg_tools")


def log_tool(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):

        # Sem args/kwargs/result no log: as tools recebem e devolvem dados do
        # usuário (alimentos, gastos, nomes). O detalhe fica no tracing, que redige PII.
        logger.info("CHAMANDO | %s", func.__name__)

        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start

        if not isinstance(result, dict):
            status = "unknown"
        else:
            status = result.get("status", "unknown")

        match status:
            case "error":
                logger.error("ERRO     | %s | elapsed=%.3fs", func.__name__, elapsed)

            case _:
                logger.info("OK       | %s | elapsed=%.3fs", func.__name__, elapsed)

        return result

    return wrapper
