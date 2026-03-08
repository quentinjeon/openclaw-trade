"""
에이전트 로그 데이터베이스 모델
"""
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AgentLog(Base):
    """에이전트 활동 로그 모델"""
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # market_analyzer | strategy | risk_manager | execution | portfolio
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    # INFO | WARNING | ERROR | DECISION | SIGNAL
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=True)    # JSON 추가 데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<AgentLog [{self.level}] {self.agent_type}: {self.message[:50]}>"
