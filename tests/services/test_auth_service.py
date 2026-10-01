from frigus_ai.infra.redis.keys import _hash_api_key
from frigus_ai.services import auth_service as auth_mod
from frigus_ai.services.auth_service import auth_service


class _FakeRedis:
    """Stub do redis-py com o `nx` do SET, que é o que garante uma key por usuário."""

    def __init__(self):
        self.dados = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.dados:
            return None
        self.dados[key] = str(value)
        return True

    def eval(self, script, numkeys, *args):
        """Emula em Python os scripts Lua de `auth_service` (cada um roda atômico no Redis)."""
        if script is auth_mod.ALOCAR_KEY:
            user_key, lookup_key, hashed, user_id, ttl = args
            if not self.set(user_key, hashed, ex=ttl, nx=True):
                return 0
            self.set(lookup_key, user_id, ex=ttl)
            return 1

        if script is auth_mod.ROTACIONAR_KEY:
            user_key, lookup_key, hashed, user_id, ttl, prefixo = args
            if (antigo := self.dados.get(user_key)) is not None:
                self.dados.pop(prefixo + antigo, None)
            self.set(user_key, hashed, ex=ttl)
            self.set(lookup_key, user_id, ex=ttl)
            return 1

        if script is auth_mod.REVOGAR_KEY:
            user_key, prefixo = args
            if (antigo := self.dados.pop(user_key, None)) is None:
                return 0
            self.dados.pop(prefixo + antigo, None)
            return 1

        raise AssertionError("script desconhecido")

    def get(self, key):
        return self.dados.get(key)


def _usar_fake_client(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("frigus_ai.services.auth_service.get_client", lambda: fake)
    return fake


def test_key_em_claro_nunca_e_persistida(monkeypatch):
    fake = _usar_fake_client(monkeypatch)

    auth_service.allocate_api_key("3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", "chave-secreta")

    assert "chave-secreta" not in str(fake.dados)
    assert _hash_api_key("chave-secreta") in str(fake.dados)


def test_lookup_devolve_o_user_id_alocado(monkeypatch):
    _usar_fake_client(monkeypatch)
    auth_service.allocate_api_key("3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", "chave-secreta")

    assert auth_service.get_user_id_by_api_key("chave-secreta") == "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"


def test_lookup_de_key_desconhecida_devolve_none(monkeypatch):
    _usar_fake_client(monkeypatch)

    assert auth_service.get_user_id_by_api_key("nunca-emitida") is None


def test_segunda_key_para_o_mesmo_usuario_e_recusada(monkeypatch):
    _usar_fake_client(monkeypatch)

    assert auth_service.allocate_api_key("3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", "primeira") is True
    assert auth_service.allocate_api_key("3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", "segunda") is False
    # a primeira continua valendo — recusar não pode invalidar a key em uso
    assert auth_service.get_user_id_by_api_key("primeira") == "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"
    assert auth_service.get_user_id_by_api_key("segunda") is None


def test_rotacionar_invalida_a_key_antiga_e_valida_a_nova(monkeypatch):
    _usar_fake_client(monkeypatch)
    auth_service.allocate_api_key("u1", "antiga")

    auth_service.rotate_api_key("u1", "nova")

    assert auth_service.get_user_id_by_api_key("antiga") is None
    assert auth_service.get_user_id_by_api_key("nova") == "u1"


def test_rotacionar_sem_key_previa_cria(monkeypatch):
    _usar_fake_client(monkeypatch)

    auth_service.rotate_api_key("u1", "nova")

    assert auth_service.get_user_id_by_api_key("nova") == "u1"


def test_revogar_apaga_a_key_e_libera_nova_alocacao(monkeypatch):
    _usar_fake_client(monkeypatch)
    auth_service.allocate_api_key("u1", "k1")

    assert auth_service.revoke_api_key("u1") is True
    assert auth_service.get_user_id_by_api_key("k1") is None
    assert auth_service.revoke_api_key("u1") is False
    assert auth_service.allocate_api_key("u1", "k2") is True


def test_hmac_muda_o_hash_e_depende_do_segredo(monkeypatch):
    from pydantic import SecretStr

    from frigus_ai.infra.redis import keys

    puro = _hash_api_key("k")
    monkeypatch.setattr(keys.settings.api_keys, "hash_secret", SecretStr("s1"))
    com_s1 = _hash_api_key("k")
    monkeypatch.setattr(keys.settings.api_keys, "hash_secret", SecretStr("s2"))

    assert len({puro, com_s1, _hash_api_key("k")}) == 3
