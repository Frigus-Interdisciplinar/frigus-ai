import functools
import time

from config.logging import get_logger

logger = get_logger("pg_tools")


def log_tool(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):

        logger.info("CHAMANDO | %s | args=%s kwargs=%s", func.__name__, args, kwargs)

        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start

        if not isinstance(result, dict):
            status = "unknown"
        else:
            status = result.get("status", "unknown")

        match status:
            case "error":
                logger.error("ERRO     | %s | elapsed=%.3fs | result=%s", func.__name__, elapsed, result)

            case _:
                logger.info("OK       | %s | elapsed=%.3fs | result=%s", func.__name__, elapsed, result)

        return result

    return wrapper
