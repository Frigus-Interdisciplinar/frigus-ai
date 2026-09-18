"""Casos de uso de UserService: bootstrap de identidade e cache-aside do perfil.
Persistência crua (Postgres/Mongo/Redis) já tem teste próprio em
tests/repositories/test_identidade_repository.py e test_user_repository.py — aqui
importa a decisão, não o banco."""

from frigus_ai.repositories import identidade_repository, user_repository
from frigus_ai.services.user_service import user_service


async def test_obter_ou_criar_padrao_reaproveita_usuario_existente(monkeypatch):
    monkeypatch.setattr(identidade_repository, "buscar_primeiro_usuario", lambda: 5)

    async def _falha_se_chamado(nome, email):
        raise AssertionError("não deveria criar usuário novo se já existe um")

    monkeypatch.setattr(user_service, "criar_usuario", _falha_se_chamado)

    assert await user_service.obter_ou_criar_padrao() == 5


async def test_obter_ou_criar_padrao_cria_quando_nao_existe_ninguem(monkeypatch):
    monkeypatch.setattr(identidade_repository, "buscar_primeiro_usuario", lambda: None)

    async def _criar_usuario(nome, email):
        return 9

    monkeypatch.setattr(user_service, "criar_usuario", _criar_usuario)

    assert await user_service.obter_ou_criar_padrao() == 9


async def test_buscar_perfil_usa_cache_quando_ha_hit(monkeypatch):
    monkeypatch.setattr(user_repository, "buscar_perfil_cache", lambda user_id: "do cache")

    def _falha_se_chamado(user_id):
        raise AssertionError("cache hit não deveria bater no Mongo")

    monkeypatch.setattr(user_repository, "buscar_perfil", _falha_se_chamado)

    assert await user_service.buscar_perfil(1) == "do cache"


async def test_buscar_perfil_cai_pro_mongo_e_popula_cache_no_miss(monkeypatch):
    monkeypatch.setattr(user_repository, "buscar_perfil_cache", lambda user_id: None)
    monkeypatch.setattr(user_repository, "buscar_perfil", lambda user_id: "do mongo")

    salvos = []
    monkeypatch.setattr(
        user_repository, "salvar_perfil_cache", lambda user_id, perfil: salvos.append((user_id, perfil))
    )

    assert await user_service.buscar_perfil(1) == "do mongo"
    assert salvos == [(1, "do mongo")]
