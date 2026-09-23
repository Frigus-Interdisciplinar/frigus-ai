"""Casos de uso de UserService: bootstrap de identidade e merge de fatos.
Persistência crua (Postgres/Mongo) já tem teste próprio em
tests/repositories/test_identidade_repository.py — aqui importa a decisão, não o banco."""

from frigus_ai.repositories import fatos_repository, identidade_repository
from frigus_ai.schemas.models import Fatos
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


async def test_atualizar_fatos_por_extracao_uniao_alergias_nunca_remove(monkeypatch):
    """Alergia é informação de segurança: mesmo que a extração não a repita, ela
    continua valendo — só `sobrescrever_fatos` (PUT manual) pode removê-la."""

    monkeypatch.setattr(
        fatos_repository, "buscar_fatos", lambda user_id: Fatos(alergias=["lactose"], habitos=["antigo"])
    )

    salvos = []
    monkeypatch.setattr(fatos_repository, "salvar_fatos", lambda user_id, fatos: salvos.append(fatos))

    extraidos = Fatos(alergias=["amendoim"], preferencias=["frango"], habitos=["novo"])
    await user_service.atualizar_fatos_por_extracao(1, extraidos)

    assert len(salvos) == 1
    salvo = salvos[0]
    assert set(salvo.alergias) == {"lactose", "amendoim"}
    # campos sem risco de segurança são substituídos pela extração mais recente, não unidos
    assert salvo.preferencias == ["frango"]
    assert salvo.habitos == ["novo"]


async def test_sobrescrever_fatos_repassa_direto_ao_repository(monkeypatch):
    """PUT manual não passa pelo merge — é o único caminho que pode remover alergia."""

    salvos = []
    monkeypatch.setattr(fatos_repository, "salvar_fatos", lambda user_id, fatos: salvos.append((user_id, fatos)))

    fatos_sem_alergia = Fatos(alergias=[])
    await user_service.sobrescrever_fatos(1, fatos_sem_alergia)

    assert salvos == [(1, fatos_sem_alergia)]
