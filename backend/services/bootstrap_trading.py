"""
TRX → USDT 전량 매도, 자동매매 부트스트랩
"""
from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from services.trade_persistence import persist_api_trade


async def sell_all_trx_to_usdt(exchange, portfolio_agent=None) -> Dict[str, Any]:
    """
    TRX/USDT 마켓에서 free TRX 전량 매도 (호가 공격 지정가).
    """
    if exchange is None or not exchange.is_connected:
        return {"ok": False, "error": "거래소 미연결"}

    sym = "TRX/USDT"
    try:
        bal = await exchange.fetch_balance()
    except Exception as e:
        logger.error(f"TRX 매도 전 잔고 조회 실패: {e}")
        return {"ok": False, "error": str(e)}

    free = float((bal.get("free") or {}).get("TRX") or 0)
    if free <= 1e-10:
        return {"ok": True, "message": "매도할 TRX 없음", "sold": 0.0}

    ex = exchange._exchange
    try:
        market = ex.market(sym)
        min_a = float(((market.get("limits") or {}).get("amount") or {}).get("min") or 0)
        if min_a > 0 and free < min_a * 0.999:
            return {"ok": True, "message": "TRX가 최소 주문 수량 미만 — 스킵", "sold": 0.0}
        amt = float(ex.amount_to_precision(sym, free))
    except Exception as e:
        logger.info(f"TRX 매도 스킵(수량/정밀도): {e}")
        return {"ok": True, "message": f"TRX 스킵: {e}", "sold": 0.0}

    if amt <= 0:
        return {"ok": True, "message": "TRX 수량이 최소 주문 미만", "sold": 0.0}

    try:
        order = await exchange.create_orderbook_limit_order(
            sym, "sell", amt, aggressive=True
        )
    except Exception as e:
        logger.error(f"TRX 매도 실패: {e}")
        return {"ok": False, "error": str(e)}

    filled = float(order.get("filled") or 0)
    avg = float(order.get("average") or order.get("price") or 0)
    if filled > 0:
        await persist_api_trade(
            symbol=sym,
            exchange_id=exchange.exchange_id,
            side="sell",
            order_kind="orderbook",
            filled=filled,
            average_price=avg,
            cost=float(order.get("cost") or filled * avg),
            fee=(
                float((order.get("fee") or {}).get("cost") or 0)
                if isinstance(order.get("fee"), dict)
                else 0.0
            ),
            is_paper=exchange.paper_trading,
            order_id=str(order.get("id", "")),
        )
    if portfolio_agent and not exchange.paper_trading:
        try:
            await portfolio_agent.run_cycle()
        except Exception as e:
            logger.warning(f"매도 후 포트폴리오 동기화: {e}")

    from main import execution_agent, risk_manager_agent

    if execution_agent and sym in execution_agent.active_positions:
        execution_agent.active_positions.pop(sym, None)
        if risk_manager_agent:
            risk_manager_agent.update_position(sym, None)

    return {
        "ok": True,
        "sold_trx": filled,
        "average_price": avg,
        "order_id": str(order.get("id", "")),
    }
