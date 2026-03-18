"""
REST 주문 API — 시장가·지정가·호가지정가, 미체결·취소·전량매도·심볼 제약·거래소 체결내역

매수/매도는 본 라우터로 직접 호출 가능합니다.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from core.config import settings
from services.trade_persistence import persist_api_trade

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _normalize_symbol(s: str) -> str:
    x = (s or "").strip().upper().replace(" ", "")
    if "/" not in x:
        raise HTTPException(status_code=400, detail="심볼은 BTC/USDT 형식이어야 합니다.")
    return x


def _fee_cost(order: Dict[str, Any]) -> float:
    fee = order.get("fee")
    if isinstance(fee, dict) and fee.get("cost") is not None:
        return float(fee["cost"])
    return 0.0


async def _portfolio_refresh():
    from main import portfolio_agent

    if portfolio_agent and not portfolio_agent.exchange.paper_trading:
        try:
            await portfolio_agent.run_cycle()
        except Exception as e:
            logger.warning(f"주문 후 포트폴리오 동기화: {e}")


def _register_tracked_buy(symbol: str, amount: float, entry: float, order_id: str) -> None:
    from main import execution_agent, risk_manager_agent

    if not execution_agent:
        return
    sl = entry * (1 - settings.DEFAULT_STOP_LOSS_PCT / 100)
    tp = entry * (1 + settings.DEFAULT_TAKE_PROFIT_PCT / 100)
    pos = {
        "symbol": symbol,
        "side": "long",
        "amount": amount,
        "entry_price": entry,
        "stop_loss": round(sl, 8),
        "take_profit": round(tp, 8),
        "trade_id": str(order_id),
        "opened_at": datetime.utcnow().isoformat() + "Z",
    }
    execution_agent.active_positions[symbol] = pos
    if risk_manager_agent:
        risk_manager_agent.update_position(symbol, pos)


def _clear_tracked_if_sold(symbol: str, side: str, sold_amount: float) -> None:
    from main import execution_agent, risk_manager_agent

    if side != "sell" or not execution_agent:
        return
    ap = execution_agent.active_positions.get(symbol)
    if not ap:
        return
    prev = float(ap.get("amount") or 0)
    if sold_amount >= prev * 0.999:
        execution_agent.active_positions.pop(symbol, None)
        if risk_manager_agent:
            risk_manager_agent.update_position(symbol, None)


async def _persist_and_refresh(
    ex,
    symbol: str,
    side: str,
    kind: str,
    order: Dict[str, Any],
) -> None:
    filled = float(order.get("filled") or 0)
    if filled <= 0:
        return
    avg = float(order.get("average") or order.get("price") or 0)
    cost = float(order.get("cost") or filled * avg)
    await persist_api_trade(
        symbol=symbol,
        exchange_id=ex.exchange_id,
        side=side,
        order_kind=kind,
        filled=filled,
        average_price=avg,
        cost=cost,
        fee=_fee_cost(order),
        is_paper=ex.paper_trading,
        order_id=str(order.get("id", "")),
    )
    await _portfolio_refresh()


# ──────────────────────────────────────────────
# 심볼 제약
# ──────────────────────────────────────────────


@router.get("/constraints/{symbol:path}")
async def order_constraints(symbol: str):
    """최소 수량·최소 명목가 등 (주문 전 검증용)"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(symbol)
    c = exchange.get_market_constraints(sym)
    if not c.get("base"):
        raise HTTPException(404, detail=f"마켓 없음: {sym}")
    return c


# ──────────────────────────────────────────────
# 주문 실행
# ──────────────────────────────────────────────


class PlaceMarketBody(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    amount: float = Field(..., gt=0)
    track_position: bool = Field(
        False,
        description="매수만: 봇 손절/익절 추적에 등록",
    )


@router.post("/market")
async def place_market_order(body: PlaceMarketBody):
    """시장가 매수/매도"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(body.symbol)
    try:
        order = await exchange.create_market_order(sym, body.side, body.amount)
    except Exception as e:
        logger.error(f"시장가 주문 실패: {e}")
        raise HTTPException(500, detail=str(e))

    await _persist_and_refresh(exchange, sym, body.side, "market", order)
    filled = float(order.get("filled") or 0)
    if body.track_position and body.side == "buy" and filled > 0:
        _register_tracked_buy(
            sym, filled, float(order.get("average") or order.get("price") or 0), order.get("id")
        )
    if body.side == "sell":
        _clear_tracked_if_sold(sym, "sell", filled)

    return {"success": True, "order": _serialize_order(order)}


class PlaceLimitBody(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    amount: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    wait_for_fill: bool = Field(
        False,
        description="True면 최대 ORDER_FILL_MAX_WAIT_SEC 동안 체결 대기",
    )
    track_position: bool = False


@router.post("/limit")
async def place_limit_order(body: PlaceLimitBody):
    """지정가 매수/매도 (wait_for_fill=False면 미체결로 오더북에만 등록)"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(body.symbol)
    ex = exchange._exchange
    price = float(ex.price_to_precision(sym, body.price))
    amt = float(ex.amount_to_precision(sym, body.amount))
    if amt <= 0:
        raise HTTPException(400, detail="수량이 최소 단위 미만입니다.")

    try:
        order = await exchange.create_limit_order(sym, body.side, amt, price)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

    oid = str(order["id"])
    if body.wait_for_fill and not exchange.paper_trading:
        deadline = time.monotonic() + float(settings.ORDER_FILL_MAX_WAIT_SEC)
        poll = float(settings.ORDER_FILL_POLL_INTERVAL_SEC)
        last = dict(order)
        while time.monotonic() < deadline:
            await asyncio.sleep(poll)
            last = await exchange.fetch_order_by_id(oid, sym)
            st = (last.get("status") or "").lower()
            filled = float(last.get("filled") or 0)
            if st in ("closed", "canceled", "cancelled") or filled >= amt * 0.999:
                break
        filled = float(last.get("filled") or 0)
        if (last.get("status") or "").lower() == "open" and filled < amt * 0.999:
            try:
                await exchange.cancel_order(oid, sym)
                last = await exchange.fetch_order_by_id(oid, sym)
            except Exception:
                pass
        order = last

    filled = float(order.get("filled") or 0)
    if filled > 0:
        await _persist_and_refresh(exchange, sym, body.side, "limit", order)
    if body.track_position and body.side == "buy" and filled > 0:
        _register_tracked_buy(sym, filled, float(order.get("average") or price), oid)
    if body.side == "sell" and filled > 0:
        _clear_tracked_if_sold(sym, "sell", filled)

    return {"success": True, "order": _serialize_order(order)}


class PlaceOrderbookBody(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    amount: float = Field(..., gt=0)
    aggressive: bool = Field(
        False,
        description="매도 긴급 시 True 권장(매수호가 쪽)",
    )
    track_position: bool = False


@router.post("/orderbook")
async def place_orderbook_order(body: PlaceOrderbookBody):
    """호가 최유리 지정가 (매수 bid / 매도 ask, aggressive 시 빠른 체결)"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(body.symbol)
    try:
        order = await exchange.create_orderbook_limit_order(
            sym, body.side, body.amount, aggressive=body.aggressive
        )
    except Exception as e:
        logger.error(f"호가 지정가 실패: {e}")
        raise HTTPException(500, detail=str(e))

    await _persist_and_refresh(exchange, sym, body.side, "orderbook", order)
    filled = float(order.get("filled") or 0)
    if body.track_position and body.side == "buy" and filled > 0:
        _register_tracked_buy(
            sym, filled, float(order.get("average") or 0), order.get("id")
        )
    if body.side == "sell":
        _clear_tracked_if_sold(sym, "sell", filled)

    return {"success": True, "order": _serialize_order(order)}


class SellAllFreeBody(BaseModel):
    symbol: str = Field(..., description="예: TRX/USDT — 베이스 코인 전량 매도")
    execution: Literal["market", "orderbook"] = "orderbook"
    aggressive: bool = True


@router.post("/sell-all-free")
async def sell_all_free_balance(body: SellAllFreeBody):
    """해당 심볼 베이스 코인의 사용 가능(free) 잔고 전량 매도"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(body.symbol)
    base = sym.split("/")[0]
    try:
        bal = await exchange.fetch_balance()
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    free = float((bal.get("free") or {}).get(base) or 0)
    if free <= 1e-12:
        raise HTTPException(400, detail=f"{base} 사용 가능 수량이 없습니다.")

    amt = float(exchange._exchange.amount_to_precision(sym, free))
    if amt <= 0:
        raise HTTPException(400, detail="매도 가능 수량이 최소 주문 미만입니다.")

    try:
        if body.execution == "market":
            order = await exchange.create_market_order(sym, "sell", amt)
            kind = "market"
        else:
            order = await exchange.create_orderbook_limit_order(
                sym, "sell", amt, aggressive=body.aggressive
            )
            kind = "orderbook"
    except Exception as e:
        raise HTTPException(500, detail=str(e))

    await _persist_and_refresh(exchange, sym, "sell", kind, order)
    _clear_tracked_if_sold(sym, "sell", float(order.get("filled") or amt))

    return {
        "success": True,
        "sold_base_amount": float(order.get("filled") or 0),
        "order": _serialize_order(order),
    }


def _serialize_order(o: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(o.get("id", "")),
        "symbol": o.get("symbol"),
        "side": o.get("side"),
        "type": o.get("type"),
        "amount": o.get("amount"),
        "filled": o.get("filled"),
        "price": o.get("price"),
        "average": o.get("average"),
        "status": o.get("status"),
        "cost": o.get("cost"),
    }


# ──────────────────────────────────────────────
# 미체결 · 취소 · 조회
# ──────────────────────────────────────────────


@router.get("/open")
async def list_open_orders(symbol: Optional[str] = Query(None)):
    """미체결 주문 목록 (symbol 생략 시 전체)"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(symbol) if symbol else None
    try:
        rows = await exchange.fetch_open_orders(sym)
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    return {"count": len(rows), "orders": [_serialize_order(dict(x)) for x in rows]}


@router.get("/status")
async def get_order_status(
    order_id: str = Query(...),
    symbol: str = Query(..., description="BTC/USDT"),
):
    """주문 단건 상태"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(symbol)
    try:
        o = await exchange.fetch_order_by_id(order_id, sym)
    except Exception as e:
        raise HTTPException(404, detail=str(e))
    return _serialize_order(dict(o))


@router.delete("/cancel")
async def cancel_one_order(
    order_id: str = Query(...),
    symbol: str = Query(...),
):
    """미체결 주문 취소"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(symbol)
    try:
        r = await exchange.cancel_order(order_id, sym)
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    return {"success": True, "result": dict(r) if isinstance(r, dict) else r}


@router.post("/cancel-all")
async def cancel_all_open(symbol: Optional[str] = Query(None)):
    """미체결 주문 전부 취소 (선택: 특정 심볼만)"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(symbol) if symbol else None
    try:
        open_o = await exchange.fetch_open_orders(sym)
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    cancelled = []
    errors = []
    for o in open_o:
        oid = str(o.get("id"))
        osym = o.get("symbol") or sym
        if not osym:
            errors.append({"id": oid, "error": "symbol missing"})
            continue
        try:
            await exchange.cancel_order(oid, osym)
            cancelled.append(oid)
        except Exception as e:
            errors.append({"id": oid, "error": str(e)})
    return {"cancelled": cancelled, "errors": errors, "count": len(cancelled)}


# ──────────────────────────────────────────────
# 거래소 최근 체결 (ccxt)
# ──────────────────────────────────────────────


@router.get("/exchange-trades")
async def list_exchange_trades(
    symbol: str = Query(..., description="BTC/USDT 등 필수 (거래소 제약)"),
    limit: int = Query(50, ge=1, le=200),
):
    """거래소 계정 최근 체결 내역 (DB trades 와 별개)"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 미연결")
    sym = _normalize_symbol(symbol)
    try:
        trades = await exchange.fetch_my_trades(sym, limit=limit)
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    out = []
    for t in trades:
        out.append(
            {
                "id": t.get("id"),
                "order": t.get("order"),
                "symbol": t.get("symbol"),
                "side": t.get("side"),
                "amount": t.get("amount"),
                "price": t.get("price"),
                "cost": t.get("cost"),
                "fee": t.get("fee"),
                "timestamp": t.get("timestamp"),
            }
        )
    return {"symbol": sym, "trades": out, "count": len(out)}
