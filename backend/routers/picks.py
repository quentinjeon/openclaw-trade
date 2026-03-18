"""
백테스트 기반 종목 추천·점수화·자동매수 설정 API

GET  /api/picks/config          설정 조회
PUT  /api/picks/config          설정 저장
POST /api/picks/scan            수동 스캔 (점수 목록)
POST /api/picks/auto-buy-once   자동매수 로직 1회 실행 (테스트용)
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from loguru import logger

from services.pick_scanner_config import (
    load_pick_scanner_config,
    save_pick_scanner_config,
    validate_symbols,
    DEFAULT_CONFIG,
)
from services.pick_auto_buy import run_pick_scan, execute_pick_auto_buy
from services.pick_scanner import result_to_dict
from services.rule_parser import STRATEGY_TEMPLATES

router = APIRouter(prefix="/api/picks", tags=["picks"])


class PickScannerConfigBody(BaseModel):
    auto_buy_enabled: Optional[bool] = None
    min_score: Optional[float] = Field(None, ge=0, le=100)
    template_key: Optional[str] = None
    condition_id: Optional[int] = None
    timeframe: Optional[str] = None
    candle_limit: Optional[int] = Field(None, ge=50, le=1000)
    symbols: Optional[List[str]] = None
    scan_interval_minutes: Optional[int] = Field(None, ge=5, le=1440)
    require_live_buy_signal: Optional[bool] = None
    max_auto_buys_per_scan: Optional[int] = Field(None, ge=1, le=10)


class ScanRequest(BaseModel):
    symbols: Optional[List[str]] = None
    timeframe: Optional[str] = None
    candle_limit: Optional[int] = Field(None, ge=50, le=1000)
    template_key: Optional[str] = None
    condition_id: Optional[int] = None


@router.get("/config")
async def get_pick_config():
    cfg = load_pick_scanner_config()
    templates = [{"key": k, "name": v["name"]} for k, v in STRATEGY_TEMPLATES.items()]
    return {"config": cfg, "template_options": templates, "defaults": DEFAULT_CONFIG}


@router.put("/config")
async def put_pick_config(body: PickScannerConfigBody):
    updates: Dict[str, Any] = {}
    data = body.model_dump(exclude_none=True)
    if "symbols" in data and data["symbols"] is not None:
        updates["symbols"] = validate_symbols(data["symbols"])
        del data["symbols"]
    updates.update(data)
    if "template_key" in updates and updates["template_key"] not in STRATEGY_TEMPLATES:
        raise HTTPException(400, detail=f"알 수 없는 template_key: {updates['template_key']}")
    cfg = save_pick_scanner_config(updates)
    return {"success": True, "config": cfg}


@router.post("/scan")
async def post_scan(body: ScanRequest = ScanRequest()):
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(503, detail="거래소 연결이 초기화되지 않았습니다.")

    base = load_pick_scanner_config()
    if body.symbols:
        base["symbols"] = validate_symbols(body.symbols)
    if body.timeframe:
        base["timeframe"] = body.timeframe
    if body.candle_limit:
        base["candle_limit"] = body.candle_limit
    if body.template_key:
        if body.template_key not in STRATEGY_TEMPLATES:
            raise HTTPException(400, detail="유효하지 않은 template_key")
        base["template_key"] = body.template_key
    if body.condition_id is not None:
        base["condition_id"] = body.condition_id

    try:
        picks = await run_pick_scan(exchange, base)
        return {
            "count": len(picks),
            "timeframe": base.get("timeframe"),
            "results": [result_to_dict(p) for p in picks],
        }
    except Exception as e:
        logger.error(f"스캔 실패: {e}")
        raise HTTPException(500, detail=str(e))


@router.post("/auto-buy-once")
async def post_auto_buy_once(
    force: bool = Query(
        False,
        description="True면 자동매수 OFF여도 점수만 맞으면 매수 시도 (페이퍼 테스트용)",
    ),
):
    try:
        return await execute_pick_auto_buy(force=force)
    except Exception as e:
        logger.error(f"auto-buy-once: {e}")
        raise HTTPException(500, detail=str(e))
