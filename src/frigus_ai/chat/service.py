import asyncio
from collections.abc import AsyncIterator

from frigus_ai.chat import repositories, runner
from frigus_ai.chat.models import ChatMessage, Role
from frigus_ai.tools.postgres.connection import get_conn
from frigus_ai.tools.postgres.helpers import next_id, resolve_stock_id
from frigus_ai.tools.redis.chat import can_send_message

# Usuário fixo para rodar a demo localmente sem tela de login. `users.id` é
# INTEGER PRIMARY KEY sem SERIAL no schema (data/sql/schema.sql), por isso
# criamos o registro (e o grupo/estoque associados) na primeira execução.
DEMO_USER_ID = 1


class LimiteDeMensagensExcedido(Exception):
    pass


def _garantir_usuario_demo(user_id: int = DEMO_USER_ID) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE id = %s;", (user_id,))
            if cur.fetchone():
                return

            cur.execute(
                """
                INSERT INTO users (id, name, account_type, email, hash_password)
                VALUES (%s, %s, 'Pessoal', %s, %s);
                """,
                (user_id, "Usuário Demo", "demo@frigus.local", "demo-hash"),
            )
            cur.execute("INSERT INTO groups (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING;", (user_id, "Minha Casa"))
            cur.execute("INSERT INTO stocks (id, group_id) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING;", (user_id, user_id))
            cur.execute(
                "INSERT INTO user_groups (id, user_id, group_id) VALUES (%s, %s, %s) ON CONFLICT (user_id, group_id) DO NOTHING;",
                (user_id, user_id, user_id),
            )
            conn.commit()


def _criar_usuario(nome: str, email: str) -> int:
    """
    Mesmo bootstrap do usuário demo (user + group + stock + vínculo), mas com id
    gerado: é o que o `POST /keys` precisa pra emitir key pra alguém que não seja
    o DEMO_USER_ID. `hash_password` é NOT NULL no schema e não há login por senha
    aqui — a credencial é a API key, guardada só como hash no Redis.
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            if existente := cur.fetchone():
                return existente[0]

            user_id = next_id(cur, "users")
            cur.execute(
                """
                INSERT INTO users (id, name, account_type, email, hash_password)
                VALUES (%s, %s, 'Pessoal', %s, 'api-key');
                """,
                (user_id, nome, email),
            )

            group_id = next_id(cur, "groups")
            cur.execute("INSERT INTO groups (id, name) VALUES (%s, %s);", (group_id, "Minha Casa"))
            cur.execute("INSERT INTO stocks (id, group_id) VALUES (%s, %s);", (next_id(cur, "stocks"), group_id))
            cur.execute(
                "INSERT INTO user_groups (id, user_id, group_id) VALUES (%s, %s, %s);",
                (next_id(cur, "user_groups"), user_id, group_id),
            )
            conn.commit()

    return user_id


async def criar_usuario(nome: str, email: str) -> int:
    return await asyncio.to_thread(_criar_usuario, nome, email)


def resolver_stock_id(user_id: int) -> int | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            return resolve_stock_id(cur, user_id)


async def iniciar_sessao(user_id: int = DEMO_USER_ID) -> int | None:
    """Garante usuário demo + perfil e resolve o stock_id. Retorna o stock_id."""
    await asyncio.to_thread(_garantir_usuario_demo, user_id)
    await repositories.garantir_perfil(user_id)

    return await asyncio.to_thread(resolver_stock_id, user_id)


async def garantir_limite(user_id: int) -> None:
    """Consome uma unidade do rate limit; levanta se o usuário estourou a janela."""

    if not await asyncio.to_thread(can_send_message, user_id):
        raise LimiteDeMensagensExcedido(
            "Você atingiu o limite de mensagens. Tente novamente em alguns instantes."
        )


async def send_message(conteudo: str, session_id: str, user_id: int, stock_id: int | None) -> str:
    await garantir_limite(user_id)

    perfil = await repositories.buscar_perfil(user_id)
    resposta = await runner.executar(conteudo, session_id, user_id, stock_id, perfil)

    if not resposta:
        return "Sem resposta."

    novas = [
        ChatMessage(role=Role.HUMAN, content=conteudo),
        ChatMessage(role=Role.AI, content=resposta),
    ]
    await repositories.salvar_mensagens(user_id, session_id, novas)

    return resposta


async def stream_message(
    conteudo: str, session_id: str, user_id: int, stock_id: int | None
) -> AsyncIterator[tuple[str, str]]:
    """
    Mesmo caso de uso do `send_message` (perfil, grafo, persistência), só que
    emitindo o progresso por nó enquanto o grafo roda.

    **Não** chama `garantir_limite` aqui de propósito: o corpo de um gerador só roda
    depois que a resposta HTTP começou, quando 429 já não é possível. Quem consome
    o limite no caminho SSE é a dependência da rota, antes de abrir o stream — e
    `can_send_message` incrementa contador, então chamar nos dois lugares cobraria
    duas mensagens por request.
    """

    perfil = await repositories.buscar_perfil(user_id)
    resposta = ""

    async for tipo, valor in runner.executar_stream(
        conteudo, session_id, user_id, stock_id, perfil
    ):
        if tipo == "resposta":
            resposta = valor
        yield tipo, valor

    novas = [
        ChatMessage(role=Role.HUMAN, content=conteudo),
        ChatMessage(role=Role.AI, content=resposta),
    ]
    await repositories.salvar_mensagens(user_id, session_id, novas)


async def get_history(session_id: str, user_id: int, limit: int = 5) -> list[ChatMessage]:
    return await repositories.buscar_historico(session_id, user_id, limit)


async def encerrar_sessao(session_id: str, user_id: int) -> None:
    await repositories.encerrar_sessao(session_id, user_id)
