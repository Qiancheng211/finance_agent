import json
from datetime import datetime
import secrets
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError

from app.finance_agent.db import SessionLocal
from app.finance_agent.models import TransactionRecord
from app.finance_agent.tables import (
    ThreadProfileTable,
    ThreadSettingTable,
    TransactionTable,
    UserIdentityTable,
    UserProfileTable,
)


def get_existing_hashes() -> set[str]:
    """查询数据库中已有交易 hash，用于去重"""
    with SessionLocal() as session:
        rows = session.execute(select(TransactionTable.raw_hash)).all()

    return {row[0] for row in rows}


def save_transactions(records: list[TransactionRecord]) -> int:
    """保存交易记录，返回成功保存数量"""
    saved_count = 0

    with SessionLocal() as session:
        for record in records:
            transaction = TransactionTable(
                transaction_time=record.transaction_time,
                merchant=record.merchant,
                description=record.description,
                amount=record.amount,
                income_expense_type=record.income_expense_type,
                category=getattr(record, "category", "未分类"),
                category_confidence=getattr(record, "category_confidence", 0.0),
                category_reason=getattr(record, "category_reason", ""),
                payment_method=record.payment_method,
                source=record.source,
                raw_hash=record.raw_hash,
                raw_data=json.dumps(record.raw_data, ensure_ascii=False, default=str),
            )

            session.add(transaction)

            try:
                session.commit()
                saved_count += 1
            except IntegrityError:
                session.rollback()

    return saved_count


def list_recent_transactions(limit: int = 10) -> list[TransactionTable]:
    """按时间倒序查询最近交易记录。"""
    with SessionLocal() as session:
        rows = session.execute(
            select(TransactionTable)
            .order_by(desc(TransactionTable.transaction_time), desc(TransactionTable.id))
            .limit(limit)
        ).scalars().all()

    return rows


def sum_amount_by_category(category: str) -> float:
    """按分类统计交易总额。"""
    with SessionLocal() as session:
        value = session.execute(
            select(func.coalesce(func.sum(TransactionTable.amount), 0.0))
            .where(TransactionTable.category == category)
        ).scalar_one()
    return float(value or 0.0)


def sum_amount_by_merchant(keyword: str) -> float:
    """按商户关键词统计交易总额。"""
    with SessionLocal() as session:
        value = session.execute(
            select(func.coalesce(func.sum(TransactionTable.amount), 0.0))
            .where(TransactionTable.merchant.ilike(f"%{keyword}%"))
        ).scalar_one()
    return float(value or 0.0)


def list_transactions(limit: int = 50, keyword: str = "", category: str = "") -> list[TransactionTable]:
    """按筛选条件查询交易。"""
    stmt = (
        select(TransactionTable)
        .order_by(desc(TransactionTable.transaction_time), desc(TransactionTable.id))
        .limit(limit)
    )

    if keyword:
        stmt = stmt.where(
            (TransactionTable.merchant.ilike(f"%{keyword}%"))
            | (TransactionTable.description.ilike(f"%{keyword}%"))
        )

    if category:
        stmt = stmt.where(TransactionTable.category == category)

    with SessionLocal() as session:
        return session.execute(stmt).scalars().all()


def update_transaction(
    transaction_id: int,
    *,
    amount: float | None = None,
    merchant: str | None = None,
    description: str | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    transaction_time: datetime | None = None,
) -> TransactionTable | None:
    """更新单条交易。"""
    with SessionLocal() as session:
        record = session.get(TransactionTable, transaction_id)
        if not record:
            return None

        if amount is not None:
            record.amount = amount
        if merchant is not None:
            record.merchant = merchant
        if description is not None:
            record.description = description
        if category is not None:
            record.category = category
        if payment_method is not None:
            record.payment_method = payment_method
        if transaction_time is not None:
            record.transaction_time = transaction_time

        session.commit()
        session.refresh(record)
        return record


def delete_transaction(transaction_id: int) -> bool:
    """删除单条交易。"""
    with SessionLocal() as session:
        record = session.get(TransactionTable, transaction_id)
        if not record:
            return False
        session.delete(record)
        session.commit()
        return True


def get_thread_setting(thread_id: str) -> ThreadSettingTable:
    """读取会话设置，不存在则创建默认值。"""
    with SessionLocal() as session:
        setting = session.execute(
            select(ThreadSettingTable).where(ThreadSettingTable.thread_id == thread_id)
        ).scalar_one_or_none()

        if setting is None:
            setting = ThreadSettingTable(thread_id=thread_id, sticker_enabled=True)
            session.add(setting)
            session.commit()
            session.refresh(setting)

        return setting


def set_thread_sticker_enabled(thread_id: str, enabled: bool) -> ThreadSettingTable:
    """设置会话表情包开关。"""
    with SessionLocal() as session:
        setting = session.execute(
            select(ThreadSettingTable).where(ThreadSettingTable.thread_id == thread_id)
        ).scalar_one_or_none()

        if setting is None:
            setting = ThreadSettingTable(thread_id=thread_id, sticker_enabled=enabled)
            session.add(setting)
        else:
            setting.sticker_enabled = enabled

        session.commit()
        session.refresh(setting)
        return setting


def get_thread_profile(thread_id: str) -> ThreadProfileTable:
    """读取会话画像，不存在则创建空画像。"""
    with SessionLocal() as session:
        profile = session.execute(
            select(ThreadProfileTable).where(ThreadProfileTable.thread_id == thread_id)
        ).scalar_one_or_none()

        if profile is None:
            profile = ThreadProfileTable(thread_id=thread_id, nickname="", gender="", habits="")
            session.add(profile)
            session.commit()
            session.refresh(profile)

        return profile


def upsert_thread_profile(
    thread_id: str,
    *,
    nickname: str | None = None,
    gender: str | None = None,
    habits: str | None = None,
) -> ThreadProfileTable:
    """更新会话画像，仅覆盖非空字段。"""
    with SessionLocal() as session:
        profile = session.execute(
            select(ThreadProfileTable).where(ThreadProfileTable.thread_id == thread_id)
        ).scalar_one_or_none()

        if profile is None:
            profile = ThreadProfileTable(thread_id=thread_id, nickname="", gender="", habits="")
            session.add(profile)

        if nickname:
            profile.nickname = nickname
        if gender:
            profile.gender = gender
        if habits:
            profile.habits = habits

        session.commit()
        session.refresh(profile)
        return profile


def get_user_profile(user_id: str) -> UserProfileTable:
    """读取用户画像，不存在则创建空画像。"""
    with SessionLocal() as session:
        profile = session.execute(
            select(UserProfileTable).where(UserProfileTable.user_id == user_id)
        ).scalar_one_or_none()

        if profile is None:
            profile = UserProfileTable(user_id=user_id, nickname="", gender="", habits="", last_thread_id="")
            session.add(profile)
            session.commit()
            session.refresh(profile)

        return profile


def upsert_user_profile(
    user_id: str,
    *,
    thread_id: str | None = None,
    nickname: str | None = None,
    gender: str | None = None,
    habits: str | None = None,
) -> UserProfileTable:
    """更新用户画像，仅覆盖非空字段；同时记录最近会话 thread_id。"""
    with SessionLocal() as session:
        profile = session.execute(
            select(UserProfileTable).where(UserProfileTable.user_id == user_id)
        ).scalar_one_or_none()

        if profile is None:
            profile = UserProfileTable(user_id=user_id, nickname="", gender="", habits="", last_thread_id="")
            session.add(profile)

        if nickname:
            profile.nickname = nickname
        if gender:
            profile.gender = gender
        if habits:
            profile.habits = habits
        if thread_id:
            profile.last_thread_id = thread_id

        session.commit()
        session.refresh(profile)
        return profile


def _generate_access_code(length: int = 10) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_user_identity() -> UserIdentityTable:
    """创建新的访问码与用户 ID。"""
    with SessionLocal() as session:
        for _ in range(10):
            candidate = UserIdentityTable(
                access_code=_generate_access_code(),
                user_id=f"user_{uuid4().hex}",
            )
            session.add(candidate)
            try:
                session.commit()
                session.refresh(candidate)
                return candidate
            except IntegrityError:
                session.rollback()
                continue
    raise RuntimeError("无法生成唯一访问码，请稍后重试")


def get_user_identity_by_access_code(access_code: str) -> UserIdentityTable | None:
    """通过访问码查询用户身份。"""
    code = (access_code or "").strip().upper()
    if not code:
        return None

    with SessionLocal() as session:
        return session.execute(
            select(UserIdentityTable).where(UserIdentityTable.access_code == code)
        ).scalar_one_or_none()
