from frigus_ai.infra.redis.connection import get_client
from frigus_ai.infra.redis.keys import (
    CHAT_TTL_TIME,
    N_MESSAGES_ACCEPTED,
    _chave_mensagem,
)
from frigus_ai.logging import Logging

logger = Logging.get_logger("redis_chat")


def can_send_message(user_id: int) -> bool:
    r = get_client()
    key = _chave_mensagem(user_id)

    result = r.incr(key)

    if result == 1:
        r.expire(key, CHAT_TTL_TIME)

    if result <= N_MESSAGES_ACCEPTED:
        return True

    logger.warning("Usuário %s excedeu o limite de mensagens.", user_id)
    return False
