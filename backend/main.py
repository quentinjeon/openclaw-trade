"""
OpenClaw Trading System - FastAPI 메인 애플리케이션
에이전트 초기화, WebSocket 엔드포인트, 라우터 등록
"""
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from core.config import settings
from core.database import init_db, AsyncSessionLocal
from core.websocket import ws_manager
from exchange.connector import ExchangeConnector
from agents.market_analyzer import MarketAnalyzerAgent, MarketSignal
from agents.strategy_agent import StrategyAgent, TradingSignal
from agents.risk_manager import RiskManagerAgent, ApprovedOrder
from agents.execution_agent import ExecutionAgent, TradeResult
from agents.portfolio_agent import PortfolioAgent, PortfolioState
from models.agent_log import AgentLog
from models.portfolio import PortfolioSnapshot

# ──────────────────────────────────────────────
# 전역 에이전트 인스턴스 (routers에서 참조)
# ──────────────────────────────────────────────
exchange: Optional[ExchangeConnector] = None
market_analyzer_agent: Optional[MarketAnalyzerAgent] = None
strategy_agent: Optional[StrategyAgent] = None
risk_manager_agent: Optional[RiskManagerAgent] = None
execution_agent: Optional[ExecutionAgent] = None
portfolio_agent: Optional[PortfolioAgent] = None

# 에이전트 실행 주기 (초)
AGENT_INTERVALS = {
    "market_analyzer": settings.MARKET_ANALYZER_INTERVAL,
    "strategy": 60,
    "risk_manager": 30,
    "execution": 10,
    "portfolio": settings.PORTFOLIO_UPDATE_INTERVAL,
}


# ──────────────────────────────────────────────
# DB 로그 저장 함수
# ──────────────────────────────────────────────
async def save_agent_log(
    agent_id: str,
    agent_type: str,
    level: str,
    message: str,
    data: Optional[str] = None,
):
    """에이전트 로그를 DB에 저장"""
    try:
        async with AsyncSessionLocal() as session:
            log = AgentLog(
                agent_id=agent_id,
                agent_type=agent_type,
                level=level,
                message=message,
                data=data,
            )
            session.add(log)
            await session.commit()

            # WebSocket으로 실시간 스트리밍
            await ws_manager.send_to_channel("agents", {
                "type": "agent_log",
                "data": {
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "level": level,
                    "message": message,
                }
            })
    except Exception as e:
        logger.error(f"에이전트 로그 DB 저장 오류: {e}")


async def save_portfolio_snapshot(portfolio: PortfolioState):
    """포트폴리오 스냅샷을 DB에 저장"""
    try:
        async with AsyncSessionLocal() as session:
            snapshot = PortfolioSnapshot(
                total_value_usd=portfolio.total_value_usd,
                cash_usd=portfolio.cash_usd,
                positions=json.dumps(portfolio.positions),
                pnl_daily=portfolio.pnl_today,
                pnl_total=portfolio.pnl_total,
                win_rate=portfolio.win_rate,
                total_trades=portfolio.total_trades,
            )
            session.add(snapshot)
            await session.commit()
    except Exception as e:
        logger.error(f"포트폴리오 스냅샷 저장 오류: {e}")


# ──────────────────────────────────────────────
# WebSocket 업데이트 함수
# ──────────────────────────────────────────────
async def on_portfolio_update(portfolio: PortfolioState):
    """포트폴리오 업데이트를 WebSocket으로 브로드캐스트"""
    await ws_manager.send_to_channel("portfolio", {
        "type": "portfolio_update",
        "data": portfolio.to_dict(),
    })


async def on_trade_result(result: TradeResult):
    """거래 결과를 WebSocket으로 브로드캐스트"""
    await ws_manager.send_to_channel("trades", {
        "type": "trade_result",
        "data": result.to_dict(),
    })


# ──────────────────────────────────────────────
# 에이전트 파이프라인 연결
# ──────────────────────────────────────────────
async def on_market_signal(signal: MarketSignal):
    """MarketAnalyzer → Strategy 파이프라인"""
    if strategy_agent:
        balance = portfolio_agent.portfolio.cash_usd if portfolio_agent else settings.PAPER_TRADING_BALANCE
        await strategy_agent.on_market_signal(signal)

    # 시장 데이터 WebSocket 전송
    await ws_manager.send_to_channel("market", {
        "type": "market_signal",
        "data": signal.to_dict(),
    })


async def on_trading_signal(signal: TradingSignal):
    """Strategy → RiskManager 파이프라인"""
    if risk_manager_agent and portfolio_agent:
        balance = portfolio_agent.portfolio.cash_usd
        await risk_manager_agent.evaluate_signal(signal, balance)


async def on_approved_order(order: ApprovedOrder):
    """RiskManager → Execution 파이프라인"""
    if execution_agent:
        await execution_agent.execute_order(order)


async def on_position_update(symbol: str, position_data: Optional[dict]):
    """Execution → RiskManager 포지션 업데이트"""
    if risk_manager_agent:
        risk_manager_agent.update_position(symbol, position_data)


async def _combined_trade_handler(result: TradeResult):
    """TradeResult → Portfolio + WebSocket"""
    if portfolio_agent:
        await portfolio_agent.on_trade_result(result)
    await on_trade_result(result)


# ──────────────────────────────────────────────
# 앱 라이프사이클
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 처리"""
    global exchange, market_analyzer_agent, strategy_agent
    global risk_manager_agent, execution_agent, portfolio_agent

    logger.info("🦅 OpenClaw Trading System 시작 중...")

    # 1. DB 초기화
    await init_db()
    logger.info("✅ 데이터베이스 초기화 완료")

    # 2. 거래소 연결
    exchange = ExchangeConnector(
        exchange_id=settings.DEFAULT_EXCHANGE,
        paper_trading=settings.PAPER_TRADING,
    )
    await exchange.initialize()
    logger.info(f"✅ 거래소 연결: {settings.DEFAULT_EXCHANGE} (paper={settings.PAPER_TRADING})")

    # 3. 에이전트 초기화 (파이프라인 연결)
    portfolio_agent = PortfolioAgent(
        exchange=exchange,
        on_update=on_portfolio_update,
    )
    portfolio_agent.set_db_callback(save_portfolio_snapshot)
    portfolio_agent.set_log_callback(save_agent_log)

    execution_agent = ExecutionAgent(
        exchange=exchange,
        on_trade_result=_combined_trade_handler,
        on_position_update=on_position_update,
    )
    execution_agent.set_log_callback(save_agent_log)

    risk_manager_agent = RiskManagerAgent(on_approve=on_approved_order)
    risk_manager_agent.set_log_callback(save_agent_log)

    strategy_agent = StrategyAgent(
        exchange=exchange,
        on_signal=on_trading_signal,
    )
    strategy_agent.set_log_callback(save_agent_log)

    market_analyzer_agent = MarketAnalyzerAgent(
        exchange=exchange,
        symbols=settings.DEFAULT_SYMBOLS,
        on_signal=on_market_signal,
    )
    market_analyzer_agent.set_log_callback(save_agent_log)

    logger.info("✅ 에이전트 파이프라인 초기화 완료")

    # 4. 에이전트 시작
    await market_analyzer_agent.start(interval_seconds=AGENT_INTERVALS["market_analyzer"])
    await execution_agent.start(interval_seconds=AGENT_INTERVALS["execution"])
    await portfolio_agent.start(interval_seconds=AGENT_INTERVALS["portfolio"])

    logger.info("🚀 OpenClaw Trading System 가동 완료!")

    yield  # 앱 실행

    # 종료 처리
    logger.info("🛑 OpenClaw Trading System 종료 중...")
    for agent in [market_analyzer_agent, strategy_agent, risk_manager_agent, execution_agent, portfolio_agent]:
        if agent:
            await agent.stop()

    if exchange:
        await exchange.close()

    logger.info("👋 OpenClaw Trading System 종료 완료")


# ──────────────────────────────────────────────
# FastAPI 앱 설정
# ──────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="OpenClaw 멀티 에이전트 암호화폐 자동매매 시스템",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
from routers import portfolio, trades, agents, settings as settings_router, market, wallet, system_trading
app.include_router(portfolio.router)
app.include_router(trades.router)
app.include_router(agents.router)
app.include_router(settings_router.router)
app.include_router(market.router)
app.include_router(wallet.router)
app.include_router(system_trading.router)


# ──────────────────────────────────────────────
# WebSocket 엔드포인트
# ──────────────────────────────────────────────
@app.websocket("/ws/portfolio")
async def websocket_portfolio(websocket: WebSocket):
    """실시간 포트폴리오 업데이트 스트림"""
    await ws_manager.connect(websocket, "portfolio")
    try:
        # 현재 상태 즉시 전송
        if portfolio_agent:
            await websocket.send_text(json.dumps({
                "type": "portfolio_update",
                "data": portfolio_agent.portfolio.to_dict(),
            }, default=str))

        while True:
            await websocket.receive_text()  # 클라이언트 ping 유지
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "portfolio")


@app.websocket("/ws/agents")
async def websocket_agents(websocket: WebSocket):
    """실시간 에이전트 로그 스트림"""
    await ws_manager.connect(websocket, "agents")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "agents")


@app.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket):
    """실시간 거래 체결 알림"""
    await ws_manager.connect(websocket, "trades")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "trades")


@app.websocket("/ws/market")
async def websocket_market(websocket: WebSocket):
    """실시간 시장 신호"""
    await ws_manager.connect(websocket, "market")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "market")


# ──────────────────────────────────────────────
# 헬스체크
# ──────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """시스템 상태 확인"""
    agents_status = {}
    for name, agent in [
        ("market_analyzer", market_analyzer_agent),
        ("strategy", strategy_agent),
        ("risk_manager", risk_manager_agent),
        ("execution", execution_agent),
        ("portfolio", portfolio_agent),
    ]:
        agents_status[name] = agent.status.value if agent else "not_initialized"

    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "paper_trading": settings.PAPER_TRADING,
        "exchange": settings.DEFAULT_EXCHANGE,
        "agents": agents_status,
    }


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
