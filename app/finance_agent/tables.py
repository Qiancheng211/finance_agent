from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.finance_agent.db import Base, engine


class TransactionTable(Base):
    """交易记录表"""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    transaction_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    income_expense_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")

    category: Mapped[str] = mapped_column(String(50), nullable=False, default="未分类")
    category_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    category_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    payment_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    raw_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    raw_data: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("raw_hash", name="uq_transactions_raw_hash"),
    )


class ThreadProfileTable(Base):
    """会话用户画像表"""

    __tablename__ = "thread_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    gender: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    habits: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class UserProfileTable(Base):
    """用户画像表（以 user_id 为主键维度，后台积累，不在前端展示）。"""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    gender: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    habits: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_thread_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class ThreadSettingTable(Base):
    """会话偏好设置表"""

    __tablename__ = "thread_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    sticker_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class UserIdentityTable(Base):
    """访问码到用户 ID 的映射表"""

    __tablename__ = "user_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    access_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


def create_tables() -> None:
    """创建数据库表"""
    Base.metadata.create_all(bind=engine)