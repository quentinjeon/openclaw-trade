"""
수동 주문 승인 대기열

리스크 통과 주문을 즉시 체결하지 않고, 사용자가 승인할 때까지 보류합니다.
"""
from typing import Dict

from fastapi import APIRouter, HTTPException
from loguru import logger

from agents.risk_manager import ApprovedOrder

router = APIRouter(prefix="/api/pending-orders", tags=["pending-orders"])


def _pending_dict() -> Dict[str, ApprovedOrder]:
    import main

    return main.PENDING_ORDERS


def _order_to_view(oid: str, o: ApprovedOrder) -> dict:
    return {
        "id": oid,
        "symbol": o.symbol,
        "side": o.side,
        "amount": o.amount,
        "order_type": o.order_type,
        "stop_loss": o.stop_loss,
        "take_profit": o.take_profit,
        "position_size_pct": o.position_size_pct,
        "reasoning": o.trading_signal.reasoning,
        "strategy_name": o.trading_signal.strategy_name,
        "confidence": o.trading_signal.confidence,
        "created_at": o.timestamp.isoformat() + "Z",
    }


@router.get("/")
async def list_pending():
    """승인 대기 중인 주문 목록"""
    import main

    if not getattr(main, "order_approval_manual", False):
        return {"manual_mode": False, "pending": [], "message": "수동 승인 모드가 꺼져 있으면 주문이 바로 체결됩니다."}
    d = _pending_dict()
    pending = [_order_to_view(oid, o) for oid, o in d.items()]
    pending.sort(key=lambda x: x["created_at"])
    return {"manual_mode": True, "pending": pending, "count": len(pending)}


@router.post("/{order_id}/approve")
async def approve_order(order_id: str):
    """대기 주문 승인 → 실제 체결 시도"""
    import main

    if not main.order_approval_manual:
        raise HTTPException(400, detail="수동 승인 모드가 꺼져 있습니다.")
    d = _pending_dict()
    if order_id not in d:
        raise HTTPException(404, detail="대기 주문을 찾을 수 없습니다.")
    order = d.pop(order_id)
    if not main.execution_agent:
        raise HTTPException(503, detail="실행 에이전트가 없습니다.")
    try:
        await main.execution_agent.execute_order(order)
        await main.ws_manager.send_to_channel("pending_orders", {"type": "removed", "id": order_id, "action": "approved"})
        logger.info(f"수동 승인 체결: {order.symbol} {order.side} {order.amount}")
        return {"success": True, "message": f"{order.symbol} 주문 실행됨", "id": order_id}
    except Exception as e:
        logger.error(f"승인 후 체결 실패: {e}")
        d[order_id] = order
        raise HTTPException(500, detail=str(e))


@router.post("/{order_id}/reject")
async def reject_order(order_id: str):
    """대기 주문 거부 (체결 안 함)"""
    import main

    d = _pending_dict()
    if order_id not in d:
        raise HTTPException(404, detail="대기 주문을 찾을 수 없습니다.")
    order = d.pop(order_id)
    await main.save_agent_log(
        "operator",
        "risk_manager",
        "INFO",
        f"[수동거부] {order.symbol} {order.side} {order.amount:.6f} — 사용자가 거부",
        None,
    )
    await main.ws_manager.send_to_channel("pending_orders", {"type": "removed", "id": order_id, "action": "rejected"})
    return {"success": True, "message": "주문이 거부되었습니다.", "id": order_id}
