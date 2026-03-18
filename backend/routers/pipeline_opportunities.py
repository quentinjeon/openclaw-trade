"""
백테스트 기반 단기 파이프라인 기회 + 활성화 시 해당 심볼 매수 자동 체결
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from services.pipeline_opportunity import scan_pipeline_opportunities

router = APIRouter(prefix="/api/pipeline-opportunities", tags=["pipeline-opportunities"])


class ActivateBody(BaseModel):
    symbol: str
    strategy_key: str = "larry_williams"


@router.get("/")
async def get_opportunities():
    """현재 유효한 기회만 (조건 불만족 시 빈 배열 → 버튼 숨김)"""
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 연결 필요")
    try:
        items = await scan_pipeline_opportunities(exchange)
        return {"opportunities": items, "computed_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"pipeline opportunities: {e}")
        raise HTTPException(500, detail=str(e))


@router.get("/active")
async def get_active_pipeline():
    """활성화된 파이프라인 (만료 시 null)"""
    import main as m

    p = getattr(m, "ACTIVE_PIPELINE", None)
    if not p:
        return {"active": None}
    vu = p.get("valid_until")
    if isinstance(vu, datetime):
        end = vu.replace(tzinfo=timezone.utc) if vu.tzinfo is None else vu.astimezone(timezone.utc)
        if datetime.now(timezone.utc) >= end:
            m.ACTIVE_PIPELINE = None
            return {"active": None}
    return {"active": _active_to_dict(p)}


def _active_to_dict(p: Dict[str, Any]) -> dict:
    vu = p.get("valid_until")
    return {
        "symbol": p.get("symbol"),
        "strategy_key": p.get("strategy_key"),
        "label": p.get("label"),
        "valid_until": vu.isoformat() if isinstance(vu, datetime) else str(vu),
        "pipeline_id": p.get("pipeline_id"),
    }


@router.post("/activate")
async def activate_pipeline(body: ActivateBody):
    """버튼 클릭: 해당 심볼 매수는 수동 승인 없이 체결(유효 시간 동안)"""
    from main import exchange
    import main as m

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 연결 필요")

    sym = body.symbol.strip().upper().replace(" ", "")
    items = await scan_pipeline_opportunities(exchange, strategy_key=body.strategy_key)
    match = next((x for x in items if x["symbol"] == sym), None)
    if not match:
        raise HTTPException(
            404,
            detail="유효한 기회가 없습니다. 조건이 바뀌었거나 표본/확률 기준을 만족하지 않습니다.",
        )

    vu = datetime.now(timezone.utc) + timedelta(minutes=int(match["window_minutes"]))
    m.ACTIVE_PIPELINE = {
        "pipeline_id": match["pipeline_id"],
        "symbol": match["symbol"],
        "strategy_key": match["strategy_key"],
        "label": match["summary"][:200],
        "valid_until": vu,
        "activated_at": datetime.now(timezone.utc),
    }
    logger.info(f"파이프라인 활성: {match['symbol']} until {vu}")
    return {"success": True, "active": _active_to_dict(m.ACTIVE_PIPELINE)}


@router.post("/deactivate")
async def deactivate_pipeline():
    import main as m

    m.ACTIVE_PIPELINE = None
    return {"success": True, "message": "파이프라인 비활성화"}


def is_pipeline_auto_buy(symbol: str) -> bool:
    """해당 심볼 BUY를 자동 체결할지"""
    import main as m

    p = getattr(m, "ACTIVE_PIPELINE", None)
    if not p or p.get("symbol") != symbol:
        return False
    vu = p.get("valid_until")
    if not isinstance(vu, datetime):
        m.ACTIVE_PIPELINE = None
        return False
    now = datetime.now(timezone.utc)
    end = vu.replace(tzinfo=timezone.utc) if vu.tzinfo is None else vu.astimezone(timezone.utc)
    if now >= end:
        m.ACTIVE_PIPELINE = None
        return False
    return True
