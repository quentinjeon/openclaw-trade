"""에이전트 관련 Pydantic 스키마"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AgentStatusResponse(BaseModel):
    """에이전트 상태 응답"""
    agent_id: str
    agent_type: str
    status: str
    total_cycles: int
    error_count: int
    last_run: Optional[datetime] = None
    started_at: Optional[datetime] = None
    is_running: bool


class AgentLogResponse(BaseModel):
    """에이전트 로그 응답"""
    id: int
    agent_id: str
    agent_type: str
    level: str
    message: str
    data: Optional[str] = None
    created_at: datetime


class StrategyConfig(BaseModel):
    """전략 설정"""
    name: str
    enabled: bool
    params: dict


class RiskConfig(BaseModel):
    """리스크 설정"""
    max_position_size_pct: float
    max_open_positions: int
    daily_loss_limit_pct: float
    stop_loss_pct: float
    take_profit_pct: float
