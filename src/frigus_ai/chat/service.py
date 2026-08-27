import asyncio

from frigus_ai.chat import repositories, runner
from frigus_ai.chat.models import ChatMessage, Role
from frigus_ai.tools.postgres.connection import get_conn
from frigus_ai.tools.postgres.helpers import resolve_stock_id
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


def _resolver_stock_id(user_id: int) -> int | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            return resolve_stock_id(cur, user_id)


async def iniciar_sessao(user_id: int = DEMO_USER_ID) -> int | None:
    """Garante usuário demo + perfil e resolve o stock_id. Retorna o stock_id."""
    await asyncio.to_thread(_garantir_usuario_demo, user_id)
    await repositories.garantir_perfil(user_id)

    return await asyncio.to_thread(_resolver_stock_id, user_id)


async def send_message(conteudo: str, session_id: str, user_id: int, stock_id: int | None) -> str:
    if not await asyncio.to_thread(can_send_message, user_id):
        raise LimiteDeMensagensExcedido(
            "Você atingiu o limite de mensagens. Tente novamente em alguns instantes."
        )

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


async def get_history(session_id: str, limit: int = 5) -> list[ChatMessage]:
    return await repositories.buscar_historico(session_id, limit)


async def encerrar_sessao(session_id: str, user_id: int) -> None:
    await repositories.encerrar_sessao(session_id, user_id)
