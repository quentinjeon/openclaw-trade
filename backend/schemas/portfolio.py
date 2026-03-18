"""포트폴리오 관련 Pydantic 스키마"""
from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel


class PositionResponse(BaseModel):
    """보유 포지션 응답"""
    symbol: str
    amount: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class PortfolioResponse(BaseModel):
    """포트폴리오 전체 응답"""
    total_value_usd: float
    cash_usd: float
    positions: Dict[str, dict]
    pnl_today: float
    pnl_total: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return_pct: float
    initial_balance: float
    updated_at: datetime
    live_trading: bool = False
    data_source: str = "simulated"  # exchange | simulated
