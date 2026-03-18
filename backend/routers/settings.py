"""
설정 API 라우터
GET /api/settings - 전체 설정 조회
PUT /api/settings/risk - 리스크 설정 변경
PUT /api/settings/strategies - 전략 설정 변경
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from schemas.agent import RiskConfig, StrategyConfig

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SystemSettings(BaseModel):
    """시스템 전체 설정"""
    paper_trading: bool
    default_exchange: str
    default_symbols: List[str]
    risk: RiskConfig
    strategies: List[StrategyConfig]


@router.get("/")
async def get_settings():
    """현재 시스템 설정 조회"""
    from main import risk_manager_agent, strategy_agent
    from core.config import settings

    risk_config = None
    if risk_manager_agent:
        risk_config = {
            "max_position_size_pct": risk_manager_agent.max_position_size_pct,
            "max_open_positions": risk_manager_agent.max_open_positions,
            "daily_loss_limit_pct": risk_manager_agent.daily_loss_limit_pct,
            "stop_loss_pct": risk_manager_agent.stop_loss_pct,
            "take_profit_pct": risk_manager_agent.take_profit_pct,
        }

    strategies_config = []
    if strategy_agent:
        for name, strategy in strategy_agent.strategies.items():
            strategies_config.append({
                "name": name,
                "enabled": strategy.enabled,
                "params": strategy.params,
                "description": strategy.description,
            })

    from services.openai_budget import get_total_spent_usd

    return {
        "paper_trading": settings.PAPER_TRADING,
        "default_exchange": settings.DEFAULT_EXCHANGE,
        "default_symbols": settings.DEFAULT_SYMBOLS,
        "risk": risk_config,
        "strategies": strategies_config,
        "fees": {
            "taker_pct_per_side": settings.TAKER_FEE_PCT_PER_SIDE,
            "round_trip_fee_pct_approx": settings.ROUND_TRIP_FEE_PCT_APPROX,
            "note": "익절 목표는 왕복 수수료·슬리피지보다 크게 잡는 것이 유리합니다.",
        },
        "openai_budget": {
            "spent_usd": round(get_total_spent_usd(), 4),
            "cap_usd": settings.OPENAI_MAX_SPEND_USD,
            "remaining_usd": round(
                max(0.0, settings.OPENAI_MAX_SPEND_USD - get_total_spent_usd()), 4
            ),
            "llm_enabled": settings.OPENAI_LLM_ENABLED,
        },
        "manual_order_approval": __import__("main").order_approval_manual,
    }


class OrderApprovalModeBody(BaseModel):
    enabled: bool


@router.put("/order-approval")
async def put_order_approval(body: OrderApprovalModeBody):
    """수동 주문 승인 ON/OFF (즉시 반영, 재시작 불필요)"""
    import main as m

    m.order_approval_manual = body.enabled
    return {
        "success": True,
        "manual_order_approval": m.order_approval_manual,
        "message": "수동 승인 ON" if body.enabled else "즉시 체결 모드(자동)",
    }


@router.put("/risk")
async def update_risk_settings(config: RiskConfig):
    """리스크 설정 업데이트"""
    from main import risk_manager_agent

    if risk_manager_agent is None:
        return {"success": False, "message": "리스크 관리 에이전트가 초기화되지 않았습니다"}

    risk_manager_agent.update_risk_params(config.model_dump())
    return {"success": True, "message": "리스크 설정 업데이트 완료", "config": config.model_dump()}


@router.put("/strategies/{strategy_name}")
async def update_strategy_settings(strategy_name: str, config: StrategyConfig):
    """전략 설정 업데이트"""
    from main import strategy_agent

    if strategy_agent is None:
        return {"success": False, "message": "전략 에이전트가 초기화되지 않았습니다"}

    strategy_agent.update_strategy_params(strategy_name, config.params)
    strategy_agent.toggle_strategy(strategy_name, config.enabled)

    return {"success": True, "message": f"{strategy_name} 전략 설정 업데이트 완료"}
