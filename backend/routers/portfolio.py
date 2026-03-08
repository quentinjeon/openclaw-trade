"""
포트폴리오 API 라우터
GET /api/portfolio - 현재 포트폴리오 조회
"""
from fastapi import APIRouter
from schemas.portfolio import PortfolioResponse

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/", response_model=PortfolioResponse)
async def get_portfolio():
    """현재 포트폴리오 상태 조회"""
    from main import portfolio_agent
    if portfolio_agent is None:
        return {
            "total_value_usd": 0.0,
            "cash_usd": 0.0,
            "positions": {},
            "pnl_today": 0.0,
            "pnl_total": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_return_pct": 0.0,
            "initial_balance": 10000.0,
            "updated_at": "2026-01-01T00:00:00",
        }
    return portfolio_agent.portfolio.to_dict()
