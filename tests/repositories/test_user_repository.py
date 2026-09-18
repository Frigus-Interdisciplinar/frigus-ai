from frigus_ai.repositories import user_repository


class _FakeRedis:
    """Stub mínimo do client redis-py — só o subset usado por user_repository.py."""

    def __init__(self):
        self._dados = {}

    def get(self, key):
        return self._dados.get(key)

    def set(self, key, value, ex=None):
        self._dados[key] = value

    def delete(self, key):
        self._dados.pop(key, None)


def _usar_fake_client(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("frigus_ai.repositories.user_repository.get_client", lambda: fake)
    return fake


def test_buscar_perfil_cache_miss(monkeypatch):
    _usar_fake_client(monkeypatch)

    assert user_repository.buscar_perfil_cache(user_id=1) is None


def test_salvar_e_buscar_perfil_cache(monkeypatch):
    _usar_fake_client(monkeypatch)

    user_repository.salvar_perfil_cache(user_id=1, perfil="gosta de receitas rápidas")

    assert user_repository.buscar_perfil_cache(user_id=1) == "gosta de receitas rápidas"


def test_invalidar_perfil_cache(monkeypatch):
    _usar_fake_client(monkeypatch)

    user_repository.salvar_perfil_cache(user_id=1, perfil="gosta de receitas rápidas")
    user_repository.invalidar_perfil_cache(user_id=1)

    assert user_repository.buscar_perfil_cache(user_id=1) is None


def test_chaves_nao_colidem_entre_usuarios(monkeypatch):
    _usar_fake_client(monkeypatch)

    user_repository.salvar_perfil_cache(user_id=1, perfil="perfil do 1")
    user_repository.salvar_perfil_cache(user_id=2, perfil="perfil do 2")

    assert user_repository.buscar_perfil_cache(user_id=1) == "perfil do 1"
    assert user_repository.buscar_perfil_cache(user_id=2) == "perfil do 2"
