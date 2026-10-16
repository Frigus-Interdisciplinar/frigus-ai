"""
Persistência crua de identidade: usuário/grupo/estoque no Postgres. Sem decisão de
negócio — isso fica em `services/user_service.py` (bootstrap de identidade).
"""

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from frigus_ai.infra.postgres.connection import PostgresRepo, transacional
from frigus_ai.infra.postgres.models import Group, Stock, User, UserGroup


class _IdentidadeRepo(PostgresRepo):
    @transacional
    def criar_usuario(self, s: Session, nome: str, email: str) -> str:
        """
        Cria usuário + grupo + estoque + vínculo (bootstrap completo). `hash_password`
        é NOT NULL no schema e não há login por senha aqui — a credencial é a API key,
        guardada só como hash no Redis (ver `services/auth_service.py`).
        """

        # A tabela tem exclusão lógica: o email só é único entre usuários não excluídos
        # (uq_users_email_active), e conta excluída não volta a valer no login.
        ativo = text("users.deleted_at IS NULL")
        por_email = select(User.id).where(User.email == email, ativo)
        if existente := s.scalar(por_email):
            return existente

        # No 1º login o app costuma disparar várias requisições juntas: todas veem que o email não
        # existe, e só uma pode inserir. As outras recebem None e usam a dela.
        user_id = s.scalar(
            insert(User)
            .values(name=nome, account_type="Pessoal", email=email, hash_password="api-key")
            .on_conflict_do_nothing(index_elements=[User.email], index_where=text("deleted_at IS NULL"))
            .returning(User.id)
        )
        if user_id is None:
            return s.scalar(por_email)

        group = Group(name="Minha Casa", owner_id=user_id)
        s.add(group)
        s.flush()  # o id do grupo vem do DEFAULT do banco

        s.add(Stock(group_id=group.id, name="Minha Casa"))
        s.add(UserGroup(user_id=user_id, group_id=group.id))

        return user_id

    @transacional
    def buscar_primeiro_usuario(self, s: Session) -> str | None:
        """Primeiro usuário que tem estoque — sem isso o modo demo pode cair num usuário sem grupo."""

        return s.scalar(
            select(User.id)
            .join(UserGroup, UserGroup.user_id == User.id)
            .join(Stock, Stock.group_id == UserGroup.group_id)
            .order_by(UserGroup.id)
            .limit(1)
        )

    @transacional
    def resolver_stock_id(self, s: Session, user_id: str) -> int | None:
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


def criar_usuario(nome: str, email: str) -> str:
    return _identidade.criar_usuario(nome, email)


def buscar_primeiro_usuario() -> str | None:
    return _identidade.buscar_primeiro_usuario()


def resolver_stock_id(user_id: str) -> int | None:
    return _identidade.resolver_stock_id(user_id)
