import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


ROOT_DIR = Path(__file__).resolve().parents[2]

load_dotenv(ROOT_DIR / "app" / ".env")
load_dotenv(ROOT_DIR / ".env")


DATABASE_URL = os.getenv("FINANCE_DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("缺少环境变量 FINANCE_DATABASE_URL，请先在 .env 中配置数据库连接字符串")


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def test_connection() -> bool:
    """测试数据库连接是否正常"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        return result.scalar() == 1