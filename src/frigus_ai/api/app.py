from fastapi import FastAPI

from frigus_ai.api.errors import register_exception_handlers
from frigus_ai.api.lifespan import lifespan
from frigus_ai.api.middleware import register_middlewares
from frigus_ai.api.routes import register_routes


def create_app() -> FastAPI:
    app = FastAPI(
        title="Frigus.AI",
        description="API do assistente conversacional do Frigus",
        version="0.1.0",
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    register_middlewares(app)
    register_routes(app)

    return app


app = create_app()
