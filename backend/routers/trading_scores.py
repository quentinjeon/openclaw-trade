"""
GET /api/trading-scores/ — 매수·매도·보유 점수 스냅샷 (대시보드)
"""
from typing import Any, Dict, List

from fastapi import APIRouter

from services.score_trading import portfolio_allocation_hint
from services.trading_score_store import trading_score_store

router = APIRouter(prefix="/api/trading-scores", tags=["trading-scores"])


@router.get("/")
async def get_trading_scores() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = trading_score_store.get_all()
    mix = portfolio_allocation_hint(rows)
    meta = trading_score_store.snapshot_meta()
    return {
        "symbols": sorted(rows, key=lambda x: x.get("symbol", "")),
        "portfolio_mix": mix,
        "meta": meta,
    }
