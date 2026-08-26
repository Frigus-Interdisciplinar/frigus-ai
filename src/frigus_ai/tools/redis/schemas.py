PROFILE_TTL_TIME = 3600
CHAT_TTL_TIME = 60
N_MESSAGES_ACCEPTED = 10


def _chave_perfil(user_id: int) -> str:
    return f"user:{user_id}:profile"


def _chave_mensagem(user_id: int) -> str:
    return f"chat:{user_id}:message"
