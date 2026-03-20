import enum
from typing import Optional

from sqlalchemy import String, DateTime, Integer, func, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from clickhouse_sqlalchemy import engines

from models.base import Base
from models.types import StringUUID


class AccountStatus(enum.StrEnum):
    PENDING = "pending"
    UNINITIALIZED = "uninitialized"
    ACTIVE = "active"
    BANNED = "banned"
    CLOSED = "closed"


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="account_pkey"),
        engines.ReplacingMergeTree()
    )

    id: Mapped[str] = mapped_column(StringUUID, server_default=func.uuid_generate_v4(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    password_salt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    coverage_analysis_permission: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    create_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
