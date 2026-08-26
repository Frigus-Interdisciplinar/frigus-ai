from fastapi import FastAPI

from interfaces.api.routes import chats_router, health_router

app = FastAPI(
    title="Frigus.AI",
    description="API do assistente conversacional do Frigus",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(chats_router)
