"""
거래(Trade) 데이터베이스 모델
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Trade(Base):
    """거래 기록 모델"""
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)        # BTC/USDT
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, index=True)      # binance
    side: Mapped[str] = mapped_column(String(4), nullable=False)                       # buy | sell
    type: Mapped[str] = mapped_column(String(10), nullable=False)                      # market | limit
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)                         # amount * price
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    # open | closed | cancelled | filled | failed
    is_paper: Mapped[bool] = mapped_column(default=True)                              # 페이퍼트레이딩 여부
    agent_id: Mapped[str] = mapped_column(String(50), nullable=True)                  # 실행 에이전트
    strategy: Mapped[str] = mapped_column(String(50), nullable=True)                  # 사용 전략
    stop_loss: Mapped[float] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float] = mapped_column(Float, nullable=True)
    close_price: Mapped[float] = mapped_column(Float, nullable=True)                  # 청산 가격
    pnl: Mapped[float] = mapped_column(Float, nullable=True)                          # 손익
    signal_data: Mapped[str] = mapped_column(Text, nullable=True)                     # JSON 신호 데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Trade {self.side} {self.amount} {self.symbol} @ {self.price}>"
