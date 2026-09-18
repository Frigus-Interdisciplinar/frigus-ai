import asyncio

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from frigus_ai.infra.mongo.connection import mongo
from frigus_ai.infra.postgres.connection import get_conn
from frigus_ai.infra.qdrant.connection import get_qdrant_client
from frigus_ai.infra.redis.connection import get_client
from frigus_ai.logging import Logging
from frigus_ai.schemas.health import HealthCheckResponse

router = APIRouter(prefix="/health", tags=["health"])
logger = Logging.get_logger(__name__)


@router.get("/live", status_code=status.HTTP_200_OK)
def liveness() -> HealthCheckResponse:
    return HealthCheckResponse(status="ok", message="service is running")


def _verificar_dependencias() -> dict[str, bool]:
    checks: dict[str, bool] = {}

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False

    try:
        mongo.client.admin.command("ping")
        checks["mongo"] = True
    except Exception:
        checks["mongo"] = False

    try:
        get_client().ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    try:
        get_qdrant_client().get_collections()
        checks["qdrant"] = True
    except Exception:
        checks["qdrant"] = False

    if not all(checks.values()):
        logger.warning("Dependência fora do ar durante /health/ready: %s", checks)

    return checks


@router.get("/ready", status_code=status.HTTP_200_OK, response_model=HealthCheckResponse)
async def readiness():
    checks = await asyncio.to_thread(_verificar_dependencias)

    if not all(checks.values()):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthCheckResponse(
                status="unavailable", message="one or more dependencies are down", checks=checks
            ).model_dump(),
        )

    return HealthCheckResponse(status="ready", message="all systems operational", checks=checks)
