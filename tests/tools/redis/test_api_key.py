from frigus_ai.tools.redis import api_key
from frigus_ai.tools.redis.schemas import _hash_api_key


class _FakeRedis:
    """Stub do redis-py com o `nx` do SET, que é o que garante uma key por usuário."""

    def __init__(self):
        self.dados = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.dados:
            return None
        self.dados[key] = str(value)
        return True

    def get(self, key):
        return self.dados.get(key)


def _usar_fake_client(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(api_key, "get_client", lambda: fake)
    return fake


def test_key_em_claro_nunca_e_persistida(monkeypatch):
    fake = _usar_fake_client(monkeypatch)

    api_key.allocate_api_key(7, "chave-secreta")

    assert "chave-secreta" not in str(fake.dados)
    assert _hash_api_key("chave-secreta") in str(fake.dados)


def test_lookup_devolve_user_id_como_int(monkeypatch):
    _usar_fake_client(monkeypatch)
    api_key.allocate_api_key(7, "chave-secreta")

    assert api_key.get_user_id_by_api_key("chave-secreta") == 7


def test_lookup_de_key_desconhecida_devolve_none(monkeypatch):
    _usar_fake_client(monkeypatch)

    assert api_key.get_user_id_by_api_key("nunca-emitida") is None


def test_segunda_key_para_o_mesmo_usuario_e_recusada(monkeypatch):
    _usar_fake_client(monkeypatch)

    assert api_key.allocate_api_key(7, "primeira") is True
    assert api_key.allocate_api_key(7, "segunda") is False
    # a primeira continua valendo — recusar não pode invalidar a key em uso
    assert api_key.get_user_id_by_api_key("primeira") == 7
    assert api_key.get_user_id_by_api_key("segunda") is None
