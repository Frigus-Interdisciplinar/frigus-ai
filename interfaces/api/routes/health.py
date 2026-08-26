from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from frigus_ai.tools.mongo.connection import banco
from frigus_ai.tools.postgres.connection import get_conn
from frigus_ai.tools.qdrant.faq.connection import get_qdrant_client
from frigus_ai.tools.redis.connection import get_client
from interfaces.api.schemas.health import HealthCheckResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", status_code=status.HTTP_200_OK)
def liveness() -> HealthCheckResponse:
    return HealthCheckResponse(status="ok", message="service is running")


@router.get("/ready", status_code=status.HTTP_200_OK, response_model=HealthCheckResponse)
def readiness():
    checks = {"postgres": False, "mongo": False, "redis": False, "qdrant": False}

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        checks["postgres"] = True

        banco.client.admin.command("ping")
        checks["mongo"] = True

        get_client().ping()
        checks["redis"] = True

        get_qdrant_client().get_collections()
        checks["qdrant"] = True

    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthCheckResponse(
                status="unavailable", message="one or more dependencies are down", checks=checks
            ).model_dump(),
        )

    return HealthCheckResponse(status="ready", message="all systems operational", checks=checks)
