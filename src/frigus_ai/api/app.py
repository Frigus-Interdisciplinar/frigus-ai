from fastapi import FastAPI

from frigus_ai.api.errors import register_exception_handlers
from frigus_ai.api.lifespan import lifespan
from frigus_ai.api.middleware import register_middlewares
from frigus_ai.api.routes import register_routes


def create_app() -> FastAPI:
    app = FastAPI(
        title="Frigus.AI",
        description="""
        API do assistente conversacional do Frigus: estoque, lista de compras, receitas e chat com agentes.

        ## Como começar

        1. **Criar a API key** — `POST /keys` com o header `X-Signup-Secret` (segredo do servidor, pedir a
        quem administra o deploy) e `{"nome", "email"}`. A `api_key` só aparece nesta resposta.
        2. **Autenticar** — mande a key em `X-API-Key` em todas as rotas `/v1`, `/a2a` e `/keys/rotate`.
        Key ausente ou inválida devolve `401`.
        3. **Conversar** — `POST /v1/chats` cria o chat; `POST /v1/chats/{chat_id}/messages` envia a mensagem
        (ou `/messages/stream` pra acompanhar a execução dos agentes via SSE).

        Rotas com limite de requisições devolvem `429` ao excedê-lo.
        """,
        openapi_tags=[
            {"name": "keys", "description": "Emissão, rotação e revogação de API key."},
            {"name": "chats", "description": "Conversa com o assistente (resposta completa ou streaming SSE)."},
            {"name": "stock", "description": "CRUD direto do estoque e análise de foto."},
            {"name": "shopping-list", "description": "Lista de compras."},
            {"name": "recipes", "description": "Receitas e sugestões com base no estoque."},
            {"name": "profile", "description": "Perfil alimentar: alergias, preferências, restrições e hábitos."},
            {"name": "health", "description": "Liveness e readiness (Postgres, Mongo, Redis, Qdrant)."},
        ],
        version="0.1.0",
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    register_middlewares(app)
    register_routes(app)

    return app


app = create_app()
