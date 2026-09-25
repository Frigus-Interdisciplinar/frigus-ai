from datetime import date

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import UUID_DEFAULT, Base, UuidStr, rotulo

AccountTypeEnum = rotulo(["Pessoal", "Empresarial", "Comercial"], ["DOMESTIC", "BUSINESS", "COMMERCIAL"])


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[UuidStr] = mapped_column(primary_key=True, server_default=UUID_DEFAULT)
    name: Mapped[str]
    banner_picture: Mapped[str | None]
    # Obrigatório pra grupo ativo (CHECK chk_active_groups_require_owner no Supabase).
    owner_id: Mapped[UuidStr | None] = mapped_column(ForeignKey("users.id"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[UuidStr] = mapped_column(primary_key=True, server_default=UUID_DEFAULT)
    name: Mapped[str]
    birth_date: Mapped[date | None]
    account_type: Mapped[str] = mapped_column(AccountTypeEnum)
    email: Mapped[str] = mapped_column(unique=True)
    hash_password: Mapped[str]


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[UuidStr] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    name: Mapped[str]


class UserGroup(Base):
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_groups_user_group"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[UuidStr] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    group_id: Mapped[UuidStr] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))


__all__ = ["Group", "Stock", "User", "UserGroup"]
