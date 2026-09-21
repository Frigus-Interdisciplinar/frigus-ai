from datetime import date

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

AccountTypeEnum = Enum("Pessoal", "Empresarial", "Convidado", name="account_type_enum")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str]
    banner_picture: Mapped[str | None]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str]
    birth_date: Mapped[date | None]
    account_type: Mapped[str] = mapped_column(AccountTypeEnum)
    email: Mapped[str] = mapped_column(unique=True)
    hash_password: Mapped[str]


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))


class UserGroup(Base):
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_groups_user_group"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))


__all__ = ["Group", "Stock", "User", "UserGroup"]
