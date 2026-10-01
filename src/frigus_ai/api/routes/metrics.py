import secrets

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from frigus_ai.settings import settings

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    # Com METRICS_TOKEN, só quem manda o Bearer (o Prometheus) lê; vazio = aberto (dev local).
    token = settings.api_keys.metrics_token.get_secret_value()
    if token and not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


__all__ = ["router"]
