"""
체결/실패 주문을 DB `trades` 테이블에 기록합니다.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict

from loguru import logger

from agents.execution_agent import TradeResult
from core.database import AsyncSessionLocal
from models.trade import Trade


def _signal_payload(result: TradeResult) -> str:
    ts = result.approved_order.trading_signal
    payload: Dict[str, Any] = {
        "reasoning": ts.reasoning,
        "confidence": ts.confidence,
        "strategy_name": ts.strategy_name,
        "exchange_order_id": result.trade_id,
    }
    if result.error:
        payload["error"] = result.error
    return json.dumps(payload, ensure_ascii=False)


async def persist_trade_result(result: TradeResult) -> None:
    """TradeResult → DB Trade 행 1건 삽입 (실패 주문도 기록)."""
    ao = result.approved_order
    ts = ao.trading_signal
    strategy = (ts.strategy_name or "")[:50] or None

    if result.status == "filled":
        status_db = "filled"
        amount = result.filled_amount
        price = result.filled_price or 0.0
        cost = result.cost
        fee = result.fee
        close_price = price if ao.side == "sell" else None
        pnl = result.realized_pnl
    else:
        status_db = "failed"
        amount = ao.amount
        price = 0.0
        cost = 0.0
        fee = 0.0
        close_price = None
        pnl = None

    trade_type = "limit" if ao.order_type == "orderbook" else ao.order_type
    if trade_type not in ("market", "limit"):
        trade_type = "limit"

    row = Trade(
        id=str(uuid.uuid4()),
        symbol=ao.symbol,
        exchange=ao.exchange,
        side=ao.side,
        type=trade_type,
        amount=amount,
        price=price,
        cost=cost,
        fee=fee,
        status=status_db,
        is_paper=result.is_paper,
        agent_id="execution",
        strategy=strategy,
        stop_loss=ao.stop_loss,
        take_profit=ao.take_profit,
        close_price=close_price,
        pnl=pnl,
        signal_data=_signal_payload(result),
    )

    try:
        async with AsyncSessionLocal() as session:
            session.add(row)
            await session.commit()
    except Exception as e:
        logger.error(f"거래 DB 저장 실패: {e}")


async def persist_api_trade(
    *,
    symbol: str,
    exchange_id: str,
    side: str,
    order_kind: str,
    filled: float,
    average_price: float,
    cost: float,
    fee: float,
    is_paper: bool,
    order_id: str,
    status: str = "filled",
) -> None:
    """REST API 등 수동 주문 체결을 DB에 기록."""
    t = "limit" if order_kind == "orderbook" else order_kind
    if t not in ("market", "limit"):
        t = "limit"
    payload = json.dumps(
        {"source": "rest_api", "exchange_order_id": order_id},
        ensure_ascii=False,
    )
    row = Trade(
        id=str(uuid.uuid4()),
        symbol=symbol,
        exchange=exchange_id,
        side=side,
        type=t,
        amount=filled,
        price=average_price,
        cost=cost if cost > 0 else filled * average_price,
        fee=fee,
        status=status,
        is_paper=is_paper,
        agent_id="api",
        strategy="manual_api",
        stop_loss=None,
        take_profit=None,
        close_price=average_price if side == "sell" else None,
        pnl=None,
        signal_data=payload,
    )
    try:
        async with AsyncSessionLocal() as session:
            session.add(row)
            await session.commit()
    except Exception as e:
        logger.error(f"API 거래 DB 저장 실패: {e}")
