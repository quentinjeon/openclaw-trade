"""
데이터베이스 연결 모듈
SQLAlchemy 2.x async 기반
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from core.config import settings


# 비동기 엔진 생성
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 기본 모델 클래스"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 의존성 주입용 DB 세션"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _sqlite_add_portfolio_columns(sync_conn) -> None:
    """기존 DB에 portfolio_snapshots 확장 컬럼 추가 (Alembic 없이)."""
    from sqlalchemy import text

    r = sync_conn.execute(text("PRAGMA table_info(portfolio_snapshots)"))
    cols = {row[1] for row in r.fetchall()}
    alters = [
        ("winning_trades", "INTEGER NOT NULL DEFAULT 0"),
        ("losing_trades", "INTEGER NOT NULL DEFAULT 0"),
        ("initial_balance", "REAL NOT NULL DEFAULT 0"),
        ("total_return_pct", "REAL NOT NULL DEFAULT 0"),
    ]
    for name, typ in alters:
        if name not in cols:
            sync_conn.execute(
                text(f"ALTER TABLE portfolio_snapshots ADD COLUMN {name} {typ}")
            )


async def init_db():
    """데이터베이스 테이블 초기화"""
    # 모델 import (테이블 생성을 위해 필요)
    from models import trade, agent_log, portfolio, system_condition  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in settings.DATABASE_URL:
            await conn.run_sync(_sqlite_add_portfolio_columns)
