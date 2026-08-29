from contextlib import asynccontextmanager

from fastapi import FastAPI

from frigus_ai.tools.spoonacular.connection import fechar_client
from interfaces.api.routes import chats_router, health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # httpx.Client segura o pool de conexões; sem isso o shutdown deixa socket
    # aberto (e o pytest reclama de recurso não fechado).
    fechar_client()


app = FastAPI(
    title="Frigus.AI",
    description="API do assistente conversacional do Frigus",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(chats_router)
