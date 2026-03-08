"""
포트폴리오 스냅샷 데이터베이스 모델
"""
from datetime import datetime
from sqlalchemy import Float, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PortfolioSnapshot(Base):
    """포트폴리오 시점 스냅샷 모델"""
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    total_value_usd: Mapped[float] = mapped_column(Float, nullable=False)    # 총 자산 (USD)
    cash_usd: Mapped[float] = mapped_column(Float, nullable=False)            # 현금 (USD)
    positions: Mapped[str] = mapped_column(Text, nullable=False)              # JSON: 보유 포지션
    pnl_daily: Mapped[float] = mapped_column(Float, default=0.0)             # 일일 손익
    pnl_total: Mapped[float] = mapped_column(Float, default=0.0)             # 총 손익
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)              # 승률 (%)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<Portfolio total={self.total_value_usd:.2f} USD, pnl={self.pnl_total:.2f}>"
