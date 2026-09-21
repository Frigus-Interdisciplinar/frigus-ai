from frigus_ai.infra.redis import rate_limit
from frigus_ai.infra.redis.keys import N_MESSAGES_ACCEPTED


class _FakeRedis:
    """Stub mínimo do client redis-py — só o subset usado por infra/redis/rate_limit.py."""

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
    monkeypatch.setattr(rate_limit, "get_client", lambda: fake)
    return fake


def test_can_send_message_dentro_do_limite(monkeypatch):
    _usar_fake_client(monkeypatch)

    for _ in range(N_MESSAGES_ACCEPTED):
        assert rate_limit.can_send_message(user_id=1) is True


def test_can_send_message_estourou_limite(monkeypatch):
    _usar_fake_client(monkeypatch)

    for _ in range(N_MESSAGES_ACCEPTED):
        rate_limit.can_send_message(user_id=1)

    assert rate_limit.can_send_message(user_id=1) is False


def test_can_send_message_seta_ttl_so_na_primeira_mensagem(monkeypatch):
    fake = _usar_fake_client(monkeypatch)

    rate_limit.can_send_message(user_id=1)
    rate_limit.can_send_message(user_id=1)

    assert fake._ttls == {"chat:1:message": 60}


def test_can_send_message_usuarios_diferentes_nao_compartilham_limite(monkeypatch):
    _usar_fake_client(monkeypatch)

    for _ in range(N_MESSAGES_ACCEPTED):
        rate_limit.can_send_message(user_id=1)

    assert rate_limit.can_send_message(user_id=2) is True
