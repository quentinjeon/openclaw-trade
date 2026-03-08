"""거래 관련 Pydantic 스키마"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TradeResponse(BaseModel):
    """거래 응답"""
    id: str
    symbol: str
    exchange: str
    side: str
    type: str
    amount: float
    price: float
    cost: float
    fee: float
    status: str
    is_paper: bool
    strategy: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl: Optional[float] = None
    created_at: datetime


class TradeListResponse(BaseModel):
    """거래 목록 응답"""
    trades: list[TradeResponse]
    total: int
