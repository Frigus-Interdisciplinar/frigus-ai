"""
Persistência crua de identidade: usuário/grupo/estoque no Postgres. Sem decisão de
negócio — isso fica em `services/user_service.py` (bootstrap de identidade).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from frigus_ai.infra.postgres.connection import PostgresRepo, transacional
from frigus_ai.infra.postgres.helpers import proximo_id
from frigus_ai.infra.postgres.models import Group, Stock, User, UserGroup


class _IdentidadeRepo(PostgresRepo):
    @transacional
    def criar_usuario(self, s: Session, nome: str, email: str) -> int:
        """
        Cria usuário + grupo + estoque + vínculo (bootstrap completo). `hash_password`
        é NOT NULL no schema e não há login por senha aqui — a credencial é a API key,
        guardada só como hash no Redis (ver `services/api_key_service.py`).
        """

        if existente := s.scalar(select(User.id).where(User.email == email)):
            return existente

        user_id = proximo_id(s, User)
        s.add(User(id=user_id, name=nome, account_type="Pessoal", email=email, hash_password="api-key"))

        group_id = proximo_id(s, Group)
        s.add(Group(id=group_id, name="Minha Casa"))
        s.add(Stock(id=proximo_id(s, Stock), group_id=group_id))
        s.add(UserGroup(id=proximo_id(s, UserGroup), user_id=user_id, group_id=group_id))

        return user_id

    @transacional
    def buscar_primeiro_usuario(self, s: Session) -> int | None:
        return s.scalar(select(User.id).order_by(User.id).limit(1))

    @transacional
    def resolver_stock_id(self, s: Session, user_id: int) -> int | None:
        """
        Resolve o stock_id do usuário: users -> user_groups -> groups -> stocks.
        Se o usuário pertencer a mais de um grupo, usa o primeiro vínculo (ORDER BY user_groups.id).
        """

        stmt = (
            select(Stock.id)
            .join(UserGroup, UserGroup.group_id == Stock.group_id)
            .where(UserGroup.user_id == user_id)
            .order_by(UserGroup.id)
            .limit(1)
        )
        return s.scalar(stmt)


_identidade = _IdentidadeRepo()


def criar_usuario(nome: str, email: str) -> int:
    return _identidade.criar_usuario(nome, email)


def buscar_primeiro_usuario() -> int | None:
    return _identidade.buscar_primeiro_usuario()


def resolver_stock_id(user_id: int) -> int | None:
    return _identidade.resolver_stock_id(user_id)
