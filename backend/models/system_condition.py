"""
시스템 트레이딩 조건식 데이터베이스 모델
사용자 정의 매수/매도 조건식을 저장합니다.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class SystemCondition(Base):
    """
    시스템 트레이딩 조건식 모델

    buy_conditions / sell_conditions은 ConditionGroup JSON을 문자열로 저장:
    {
      "logic": "AND",
      "conditions": [
        {
          "id": "cond_1",
          "indicator_a": "RSI",
          "params_a": {"period": 14},
          "operator": "<=",
          "type_b": "value",
          "value_b": 30
        }
      ]
    }
    """
    __tablename__ = "system_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 기본 정보
    name: Mapped[str] = mapped_column(String(100), nullable=False)          # "내 BTC 전략 v1"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 사용자 설명

    # 대상 설정
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, default="BTC/USDT")
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False, default="1h")

    # 조건식 JSON (ConditionGroup)
    buy_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON
    sell_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # 활성화 여부 (실시간 모니터링)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 마지막 백테스트 결과 캐시
    backtest_win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    backtest_total_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    backtest_avg_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    backtest_max_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    backtest_ran_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<SystemCondition id={self.id} name='{self.name}' symbol={self.symbol}>"
