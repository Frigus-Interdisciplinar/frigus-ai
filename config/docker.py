import atexit
import subprocess
import time

from config.logging import get_logger

logger = get_logger("docker")

# Serviços definidos em docker-compose.yml: postgres, mongo, redis, qdrant
COMPOSE_FILE = "docker-compose.yml"


def _garantir_daemon():

    resultado = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        check=False,  # returncode != 0 é esperado (daemon desligado)
    )

    if resultado.returncode == 0:
        return

    logger.info("Subindo Docker Desktop...")
    subprocess.Popen(["C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"])

    for _ in range(30):
        time.sleep(3)

        check = subprocess.run(["docker", "info"], capture_output=True, check=False)
        if check.returncode == 0:
            logger.info("Docker Desktop pronto.")
            return

    raise RuntimeError("Docker Desktop não respondeu após 90 segundos.")


def _encerrar_servicos():

    logger.info("Encerrando serviços do docker-compose (%s)...", COMPOSE_FILE)
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "stop"], check=True)
    logger.info("Serviços encerrados.")


def garantir_banco() -> None:
    """
    Sobe (se necessário) os serviços do docker-compose: postgres, mongo, redis, qdrant.
    Registra o encerramento automático quando o processo terminar.
    """

    _garantir_daemon()

    resultado = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "ps", "--status", "running", "--services"],
        capture_output=True,
        text=True,
        check=False,  # a saída é inspecionada abaixo, não o returncode
    )

    servicos_rodando = set(resultado.stdout.split())
    servicos_esperados = {"postgres", "mongo", "redis", "qdrant"}

    if servicos_esperados.issubset(servicos_rodando):
        logger.info("Todos os serviços já estão rodando.")
        return

    logger.info("Subindo serviços via docker compose...")
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"], check=True)
    logger.info("Serviços prontos.")

    # quando o app fecha, desliga os containers
    atexit.register(_encerrar_servicos)
