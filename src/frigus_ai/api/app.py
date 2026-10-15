from inspect import cleandoc

from fastapi import FastAPI

from frigus_ai.api.errors import register_exception_handlers
from frigus_ai.api.lifespan import lifespan
from frigus_ai.api.middleware import register_middlewares
from frigus_ai.api.routes import register_routes


def create_app() -> FastAPI:
    app = FastAPI(
        title="Frigus.AI",
        description=cleandoc("""
            API do assistente conversacional do Frigus, um aplicativo de gestão de alimentos. Ela dá
            acesso ao estoque da geladeira, do freezer e da despensa, à lista de compras, a receitas
            sugeridas com o que já existe em casa e ao perfil alimentar de cada usuário: alergias,
            preferências e restrições.

            O centro da API é o chat. Cada mensagem passa por um conjunto de agentes que entende o
            pedido, consulta ou altera os dados do usuário e devolve uma resposta em texto, conferida
            contra esses dados antes de ser entregue. A resposta pode vir completa ou em streaming
            (SSE), que também mostra a execução dos agentes em tempo real. As rotas de estoque, compras,
            receitas e perfil usam os mesmos dados e podem ser chamadas diretamente, sem passar pelo chat.

            **Autenticação.** Há duas formas de se identificar, e todas as rotas protegidas aceitam
            qualquer uma delas. A primeira é o login do app Frigus: envie o token do Firebase no header
            Authorization, no formato Bearer. O usuário é reconhecido pelo email verificado e criado
            automaticamente no primeiro acesso. A segunda é a API key, pensada para integrações e
            máquinas: envie a key no header X-API-Key.

            Para criar uma key, chame POST /keys com o header X-Signup-Secret, um segredo do servidor
            que você pede a quem administra o deploy, e o corpo com nome e email. A key aparece uma única
            vez na resposta. Depois ela pode ser trocada em POST /keys/rotate ou revogada com
            DELETE /keys. Credencial ausente ou inválida devolve 401. As rotas de health e o Agent Card
            não exigem autenticação, e o servidor MCP aceita apenas a API key. Em ambiente local, o
            servidor pode rodar com a autenticação desligada, e então todas as rotas usam um usuário
            local único.

            **Limites.** Cada usuário pode enviar até 10 mensagens por minuto no chat, e a criação de
            keys é limitada a 5 por hora por IP. Ao exceder um limite, a API devolve 429.

            **Erros.** Erros de regra de negócio vêm com os campos detail, code e request_id. Erros de
            validação (422) trazem detail como uma lista, com o campo e o motivo de cada falha.

            **Outras interfaces.** Além desta API REST, o Frigus expõe suas ferramentas por MCP e conversa
            com outros agentes pelo protocolo A2A.
        """),
        openapi_tags=[
            {"name": "keys", "description": "Emissão, rotação e revogação de API key (a emissão exige o segredo de cadastro)."},
            {"name": "chats", "description": "Conversa com o assistente (resposta completa ou streaming SSE)."},
            {"name": "stock", "description": "CRUD direto do estoque e análise de foto."},
            {"name": "shopping-list", "description": "Lista de compras."},
            {"name": "recipes", "description": "Receitas e sugestões com base no estoque."},
            {"name": "profile", "description": "Perfil alimentar: alergias, preferências, restrições e hábitos."},
            {"name": "a2a", "description": "Agent Card e mensagens do protocolo A2A (agente remoto)."},
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
