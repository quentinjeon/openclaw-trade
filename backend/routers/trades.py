"""
거래 내역 API 라우터
GET /api/trades - 거래 내역 조회
POST /api/trades/close-all - 전체 포지션 청산
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.trade import Trade
from schemas.trade import TradeListResponse, TradeResponse

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("/", response_model=TradeListResponse)
async def get_trades(
    symbol: Optional[str] = Query(None, description="필터: 심볼"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """거래 내역 조회"""
    query = select(Trade).order_by(desc(Trade.created_at))

    if symbol:
        query = query.where(Trade.symbol == symbol)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    trades = result.scalars().all()

    trade_responses = [
        TradeResponse(
            id=t.id,
            symbol=t.symbol,
            exchange=t.exchange,
            side=t.side,
            type=t.type,
            amount=t.amount,
            price=t.price,
            cost=t.cost,
            fee=t.fee or 0.0,
            status=t.status,
            is_paper=t.is_paper,
            strategy=t.strategy,
            stop_loss=t.stop_loss,
            take_profit=t.take_profit,
            pnl=t.pnl,
            created_at=t.created_at,
        )
        for t in trades
    ]

    return TradeListResponse(trades=trade_responses, total=len(trade_responses))


@router.post("/close-all")
async def close_all_positions():
    """전체 포지션 긴급 청산"""
    from main import execution_agent
    if execution_agent:
        await execution_agent.close_all_positions()
        return {"message": "전체 포지션 청산 완료", "success": True}
    return {"message": "실행 에이전트가 초기화되지 않았습니다", "success": False}
