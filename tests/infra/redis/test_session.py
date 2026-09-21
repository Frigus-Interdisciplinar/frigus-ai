from frigus_ai.infra.redis import session
from frigus_ai.infra.redis.keys import SESSION_TTL_TIME


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.calls = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        self.calls.append((key, value, ex, nx))
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True


def _usar_fake_client(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(session, "get_client", lambda: fake)
    return fake


def test_buscar_usuario_da_sessao_retorna_id(monkeypatch):
    fake = _usar_fake_client(monkeypatch)
    fake.values["a2a:context:ctx-1"] = "42"

    assert session.buscar_usuario_da_sessao("ctx-1") == 42


def test_salvar_usuario_da_sessao_e_atomico_e_tem_ttl(monkeypatch):
    fake = _usar_fake_client(monkeypatch)

    assert session.salvar_usuario_da_sessao("ctx-1", 42) is True
    assert session.salvar_usuario_da_sessao("ctx-1", 99) is False
    assert fake.values["a2a:context:ctx-1"] == "42"
    assert fake.calls[0] == ("a2a:context:ctx-1", 42, SESSION_TTL_TIME, True)
