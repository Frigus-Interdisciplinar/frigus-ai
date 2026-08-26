from frigus_ai.tools.redis import chat
from frigus_ai.tools.redis.schemas import N_MESSAGES_ACCEPTED


class _FakeRedis:
    """Stub mínimo do client redis-py — só o subset usado por tools/redis/chat.py."""

    def __init__(self):
        self._contadores = {}
        self._ttls = {}

    def incr(self, key):
        self._contadores[key] = self._contadores.get(key, 0) + 1
        return self._contadores[key]

    def expire(self, key, seconds):
        self._ttls[key] = seconds


def _usar_fake_client(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(chat, "get_client", lambda: fake)
    return fake


def test_can_send_message_dentro_do_limite(monkeypatch):
    _usar_fake_client(monkeypatch)

    for _ in range(N_MESSAGES_ACCEPTED):
        assert chat.can_send_message(user_id=1) is True


def test_can_send_message_estourou_limite(monkeypatch):
    _usar_fake_client(monkeypatch)

    for _ in range(N_MESSAGES_ACCEPTED):
        chat.can_send_message(user_id=1)

    assert chat.can_send_message(user_id=1) is False


def test_can_send_message_seta_ttl_so_na_primeira_mensagem(monkeypatch):
    fake = _usar_fake_client(monkeypatch)

    chat.can_send_message(user_id=1)
    chat.can_send_message(user_id=1)

    assert fake._ttls == {"chat:1:message": 60}


def test_can_send_message_usuarios_diferentes_nao_compartilham_limite(monkeypatch):
    _usar_fake_client(monkeypatch)

    for _ in range(N_MESSAGES_ACCEPTED):
        chat.can_send_message(user_id=1)

    assert chat.can_send_message(user_id=2) is True
