"""
OpenClaw Trading System - FastAPI 메인 애플리케이션
에이전트 초기화, WebSocket 엔드포인트, 라우터 등록
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Optional

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
from services.trade_persistence import persist_trade_result

# ──────────────────────────────────────────────
# 전역 에이전트 인스턴스 (routers에서 참조)
# ──────────────────────────────────────────────
exchange: Optional[ExchangeConnector] = None
market_analyzer_agent: Optional[MarketAnalyzerAgent] = None
strategy_agent: Optional[StrategyAgent] = None
risk_manager_agent: Optional[RiskManagerAgent] = None
execution_agent: Optional[ExecutionAgent] = None
portfolio_agent: Optional[PortfolioAgent] = None

# 수동 주문 승인 대기열 (order_id -> ApprovedOrder)
PENDING_ORDERS: Dict[str, ApprovedOrder] = {}
# 런타임 토글 (설정 API에서 변경 가능)
order_approval_manual: bool = True
# 대시보드 파이프라인 활성화 시: 해당 심볼 BUY 자동 체결 (유효 시간 내)
ACTIVE_PIPELINE: Optional[dict] = None

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
                winning_trades=portfolio.winning_trades,
                losing_trades=portfolio.losing_trades,
                initial_balance=portfolio.initial_balance,
                total_return_pct=portfolio.total_return_pct,
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
        "data": portfolio_agent.get_summary() if portfolio_agent else portfolio.to_dict(live_trading=False),
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
    """RiskManager → 매도는 즉시 체결 → (파이프라인 자동 매수) → (수동 승인) → Execution"""
    if order.side == "sell":
        if execution_agent:
            await execution_agent.execute_order(order)
        await save_agent_log(
            "risk_manager",
            "execution",
            "DECISION",
            f"[자동 청산] {order.symbol} 매도 {order.amount:.8f}",
            order.to_dict(),
        )
        return

    if order.side == "buy":
        from routers.pipeline_opportunities import is_pipeline_auto_buy

        if is_pipeline_auto_buy(order.symbol):
            if execution_agent:
                await execution_agent.execute_order(order)
            await save_agent_log(
                "pipeline",
                "execution",
                "DECISION",
                f"[파이프라인 자동체결] {order.symbol} {order.amount:.6f}",
                None,
            )
            return

    if order_approval_manual:
        oid = str(uuid.uuid4())
        PENDING_ORDERS[oid] = order
        await save_agent_log(
            "system",
            "execution",
            "INFO",
            f"[승인 대기] {order.symbol} {order.side} {order.amount:.6f} — 대시보드에서 승인하세요",
            None,
        )
        await ws_manager.send_to_channel(
            "pending_orders",
            {
                "type": "new_pending",
                "pending": {
                    "id": oid,
                    "symbol": order.symbol,
                    "side": order.side,
                    "amount": order.amount,
                    "reasoning": order.trading_signal.reasoning,
                    "strategy_name": order.trading_signal.strategy_name,
                },
            },
        )
        return
    if execution_agent:
        await execution_agent.execute_order(order)


async def on_position_update(symbol: str, position_data: Optional[dict]):
    """Execution → RiskManager 포지션 업데이트"""
    if risk_manager_agent:
        risk_manager_agent.update_position(symbol, position_data)


async def _combined_trade_handler(result: TradeResult):
    """TradeResult → Portfolio + DB + WebSocket"""
    if portfolio_agent:
        await portfolio_agent.on_trade_result(result)
    await persist_trade_result(result)
    await on_trade_result(result)


# ──────────────────────────────────────────────
# 앱 라이프사이클
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 처리"""
    global exchange, market_analyzer_agent, strategy_agent
    global risk_manager_agent, execution_agent, portfolio_agent
    global order_approval_manual

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
    logger.info(
        f"✅ 거래소 연결: {settings.DEFAULT_EXCHANGE} (paper={settings.PAPER_TRADING}, testnet={settings.BINANCE_TESTNET})"
    )

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
    portfolio_agent.attach_execution_agent(execution_agent)

    if not settings.PAPER_TRADING:
        logger.info("실거래 모드 (현물 메인넷 기준 잔고 동기화)")
        if not (settings.BINANCE_API_KEY and settings.BINANCE_SECRET_KEY):
            logger.warning("BINANCE API 키 미설정 시 잔고·주문 API가 실패합니다.")
        try:
            await portfolio_agent.run_cycle()
        except Exception as e:
            logger.error(f"초기 거래소 잔고 동기화 실패: {e}")

    risk_manager_agent = RiskManagerAgent(on_approve=on_approved_order)
    risk_manager_agent.set_log_callback(save_agent_log)
    risk_manager_agent.set_connector(exchange)

    async def on_holdings_strategy_exit(ts):
        """보유 종목 전용 Williams %R 매도 신호 → 리스크 → 즉시 매도"""
        if risk_manager_agent and portfolio_agent:
            await risk_manager_agent.evaluate_signal(
                ts, portfolio_agent.portfolio.cash_usd
            )

    execution_agent.on_strategy_exit = on_holdings_strategy_exit

    strategy_agent = StrategyAgent(
        exchange=exchange,
        on_signal=on_trading_signal,
    )
    strategy_agent.set_log_callback(save_agent_log)

    def _position_info_for_strategy(sym: str):
        if risk_manager_agent and sym in risk_manager_agent.open_positions:
            return risk_manager_agent.open_positions[sym]
        return None

    strategy_agent.set_position_info_getter(_position_info_for_strategy)

    market_analyzer_agent = MarketAnalyzerAgent(
        exchange=exchange,
        symbols=settings.DEFAULT_SYMBOLS,
        on_signal=on_market_signal,
    )
    market_analyzer_agent.set_log_callback(save_agent_log)

    order_approval_manual = settings.MANUAL_ORDER_APPROVAL
    logger.info(
        f"✅ 에이전트 파이프라인 초기화 완료 (수동 주문 승인={'ON' if order_approval_manual else 'OFF'})"
    )

    # 4. (선택) TRX→USDT 정리 후 전 에이전트 가동
    if getattr(settings, "STARTUP_BOOTSTRAP_TRADING", False):
        from services.bootstrap_trading import sell_all_trx_to_usdt

        tr = await sell_all_trx_to_usdt(exchange, portfolio_agent)
        logger.info(f"기동 부트스트랩 TRX: {tr}")

    await market_analyzer_agent.start(interval_seconds=AGENT_INTERVALS["market_analyzer"])
    await strategy_agent.start(interval_seconds=60)
    await risk_manager_agent.start(interval_seconds=30)
    await execution_agent.start(interval_seconds=AGENT_INTERVALS["execution"])
    await portfolio_agent.start(interval_seconds=AGENT_INTERVALS["portfolio"])

    logger.info("🚀 OpenClaw Trading System 가동 완료! (시장분석·전략·리스크·체결·포트폴리오)")

    async def pick_scanner_loop():
        """백테스트 스캐너 자동매수 (설정에서 켠 경우에만 매수 시도)"""
        from services.pick_scanner_config import load_pick_scanner_config
        from services.pick_auto_buy import execute_pick_auto_buy

        await asyncio.sleep(90)
        while True:
            try:
                interval = int(load_pick_scanner_config().get("scan_interval_minutes") or 60)
                interval = max(5, min(interval, 1440))
                await execute_pick_auto_buy(force=False)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"PickScanner 루프 오류: {e}")
            try:
                await asyncio.sleep(interval * 60)
            except asyncio.CancelledError:
                break

    pick_scanner_task = asyncio.create_task(pick_scanner_loop())

    async def trading_scores_refresh_loop():
        """대시보드 점수 패널용: 감시 심볼·보유 심볼 주기 갱신"""
        import pandas as pd
        from services.score_trading import compute_trading_scores
        from services.trading_score_store import trading_score_store

        await asyncio.sleep(18)
        while True:
            try:
                from core.stable_coins import STABLE_COINS

                syms = set(settings.DEFAULT_SYMBOLS or [])
                if risk_manager_agent:
                    syms |= set(risk_manager_agent.open_positions.keys())
                if not exchange.paper_trading:
                    try:
                        bal = await exchange.fetch_balance()
                        for cur, amt in (bal.get("total") or {}).items():
                            if float(amt or 0) > 0 and cur not in STABLE_COINS:
                                syms.add(f"{cur}/USDT")
                    except Exception:
                        pass
                for sym in syms:
                    try:
                        ohlcv = await exchange.fetch_ohlcv(
                            sym, timeframe="1h", limit=200
                        )
                        if not ohlcv or len(ohlcv) < 50:
                            continue
                        df = pd.DataFrame(
                            ohlcv,
                            columns=[
                                "timestamp",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                            ],
                        )
                        df["timestamp"] = pd.to_datetime(
                            df["timestamp"], unit="ms"
                        )
                        df = df.set_index("timestamp")
                        tk = await exchange.fetch_ticker(sym)
                        px = float(tk.get("last") or tk.get("close") or 0)
                        pi = (
                            risk_manager_agent.open_positions.get(sym)
                            if risk_manager_agent
                            else None
                        )
                        has = bool(pi)
                        entry = float(pi.get("entry_price") or 0) if pi else None
                        ms = MarketSignal(
                            symbol=sym,
                            exchange=exchange.exchange_id,
                            direction="NEUTRAL",
                            confidence=0.5,
                            indicators={},
                            price=px,
                            volume_24h=float(tk.get("quoteVolume") or 0),
                        )
                        sc = compute_trading_scores(
                            df, ms, has, entry, px
                        )
                        trading_score_store.update(
                            sym, sc.to_public_dict(sym, has)
                        )
                    except Exception as e:
                        logger.warning(f"매매점수 갱신 실패 {sym}: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"trading_scores_refresh_loop: {e}")
            try:
                await asyncio.sleep(50)
            except asyncio.CancelledError:
                break

    scores_task = asyncio.create_task(trading_scores_refresh_loop())

    yield  # 앱 실행

    # 종료 처리
    logger.info("🛑 OpenClaw Trading System 종료 중...")
    scores_task.cancel()
    try:
        await scores_task
    except asyncio.CancelledError:
        pass
    pick_scanner_task.cancel()
    try:
        await pick_scanner_task
    except asyncio.CancelledError:
        pass
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
from routers import (
    portfolio,
    trades,
    orders,
    agents,
    settings as settings_router,
    market,
    wallet,
    system_trading,
    picks,
    pending_orders,
    pipeline_opportunities,
    trading_scores,
)
app.include_router(portfolio.router)
app.include_router(orders.router)
app.include_router(trades.router)
app.include_router(agents.router)
app.include_router(settings_router.router)
app.include_router(market.router)
app.include_router(wallet.router)
app.include_router(system_trading.router)
app.include_router(picks.router)
app.include_router(pending_orders.router)
app.include_router(pipeline_opportunities.router)
app.include_router(trading_scores.router)


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
                "data": portfolio_agent.get_summary(),
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


@app.websocket("/ws/pending-orders")
async def websocket_pending_orders(websocket: WebSocket):
    """승인 대기 주문 알림"""
    await ws_manager.connect(websocket, "pending_orders")
    try:
        import main as m

        pending = [
            {"id": oid, "symbol": o.symbol, "side": o.side, "amount": o.amount}
            for oid, o in m.PENDING_ORDERS.items()
        ]
        await websocket.send_text(
            json.dumps({"type": "snapshot", "pending": pending}, default=str)
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "pending_orders")


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
