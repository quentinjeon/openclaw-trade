"""
ExecutionAgent - 실제 주문 실행 에이전트
ApprovedOrder를 받아 거래소에 주문을 실행합니다.
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agents.strategy_agent import TradingSignal

from loguru import logger

from agents.base_agent import BaseAgent
from agents.risk_manager import ApprovedOrder
from core.config import settings
from exchange.connector import ExchangeConnector


@dataclass
class TradeResult:
    """주문 실행 결과"""
    trade_id: str
    approved_order: ApprovedOrder
    status: str             # filled | failed | cancelled
    filled_amount: float
    filled_price: float
    cost: float
    fee: float
    is_paper: bool
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    realized_pnl: Optional[float] = None  # 매도 체결 시 실현손익 (DB trades.pnl)

    def to_dict(self) -> dict:
        d = {
            "trade_id": self.trade_id,
            "symbol": self.approved_order.symbol,
            "side": self.approved_order.side,
            "status": self.status,
            "filled_amount": self.filled_amount,
            "filled_price": self.filled_price,
            "cost": self.cost,
            "fee": self.fee,
            "stop_loss": self.approved_order.stop_loss,
            "take_profit": self.approved_order.take_profit,
            "is_paper": self.is_paper,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.realized_pnl is not None:
            d["realized_pnl"] = self.realized_pnl
        return d


class ExecutionAgent(BaseAgent):
    """
    주문 실행 에이전트
    
    역할:
    - 승인된 주문을 거래소에 실행
    - 손절/익절 주문 자동 설정
    - 주문 체결 확인
    - 실행 결과를 PortfolioAgent에 전달
    - 포지션 정보를 RiskManagerAgent에 업데이트
    """

    agent_type = "execution"

    def __init__(
        self,
        exchange: ExchangeConnector,
        on_trade_result: Optional[Callable[[TradeResult], None]] = None,
        on_position_update: Optional[Callable[[str, Optional[dict]], None]] = None,
        on_strategy_exit: Optional[Callable[["TradingSignal"], Awaitable[None]]] = None,
    ):
        super().__init__()
        self.exchange = exchange
        self.on_trade_result = on_trade_result
        self.on_position_update = on_position_update
        self.on_strategy_exit = on_strategy_exit

        # 활성 포지션 추적
        self.active_positions: Dict[str, dict] = {}
        self._exit_tick: int = 0
        self._last_strategy_exit_attempt: Dict[str, datetime] = {}

    async def run_cycle(self):
        """손절/익절 → 전략 매도 신호(보유 종목 전용)"""
        if not self.active_positions:
            return

        await self._log("INFO", f"포지션 모니터링: {len(self.active_positions)}개")

        for symbol, position in list(self.active_positions.items()):
            try:
                await self._check_stop_loss_take_profit(symbol, position)
            except Exception as e:
                await self._log("ERROR", f"{symbol} 포지션 체크 오류: {e}")

        await self._scan_strategy_exit_signals()

    async def _scan_strategy_exit_signals(self):
        """
        보유 중인 심볼만 대상으로 Larry Williams %R 등 매도 신호 주기 점검.
        시장 분석 대상 심볼 목록에 없어도 청산 신호를 받을 수 있게 함.
        """
        if not self.active_positions or not self.on_strategy_exit:
            return

        self._exit_tick += 1
        if self._exit_tick % 6 != 0:
            return

        import pandas as pd
        from strategies import AVAILABLE_STRATEGIES
        from agents.market_analyzer import MarketSignal
        from agents.strategy_agent import TradingSignal

        strat_cls = AVAILABLE_STRATEGIES.get("larry_williams")
        if not strat_cls:
            return
        strat = strat_cls()
        strat.enabled = True

        from datetime import timedelta

        for symbol, position in list(self.active_positions.items()):
            last = self._last_strategy_exit_attempt.get(symbol)
            if last and (datetime.utcnow() - last) < timedelta(seconds=50):
                continue
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe="1h", limit=200)
                if not ohlcv or len(ohlcv) < 50:
                    continue
                df = pd.DataFrame(
                    ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("timestamp")
                sig = strat.generate_signal(df)
                if sig.action != "SELL":
                    continue
                from services.score_trading import compute_trading_scores

                ticker = await self.exchange.fetch_ticker(symbol)
                px = float(ticker.get("last") or ticker.get("close") or 0)
                entry = float(position.get("entry_price") or 0)
                ms_chk = MarketSignal(
                    symbol=symbol,
                    exchange=self.exchange.exchange_id,
                    direction="NEUTRAL",
                    confidence=0.5,
                    indicators={},
                    price=px,
                    volume_24h=float(ticker.get("quoteVolume") or 0),
                )
                scx = compute_trading_scores(
                    df, ms_chk, True, entry if entry > 0 else None, px
                )
                if scx.sell_score <= scx.hold_score + 4:
                    continue
                self._last_strategy_exit_attempt[symbol] = datetime.utcnow()
                ms = MarketSignal(
                    symbol=symbol,
                    exchange=self.exchange.exchange_id,
                    direction="NEUTRAL",
                    confidence=0.55,
                    indicators=sig.indicators,
                    price=px,
                    volume_24h=float(ticker.get("quoteVolume") or 0),
                )
                ts = TradingSignal(
                    symbol=symbol,
                    exchange=self.exchange.exchange_id,
                    action="SELL",
                    strategy_name="larry_williams",
                    confidence=max(0.58, min(0.95, sig.confidence)),
                    reasoning=f"[보유자동청산] {sig.reasoning}",
                    market_signal=ms,
                    indicators=sig.indicators,
                )
                await self._log(
                    "SIGNAL",
                    f"{symbol} 보유 포지션 매도 신호 → 리스크 검토",
                    {"reasoning": sig.reasoning},
                )
                await self.on_strategy_exit(ts)
            except Exception as e:
                await self._log("ERROR", f"{symbol} 청산 신호 스캔 오류: {e}")

    async def execute_order(self, approved_order: ApprovedOrder):
        """승인된 주문 실행"""
        symbol = approved_order.symbol

        await self._log(
            "INFO",
            f"{symbol} 주문 실행 시작: {approved_order.side} {approved_order.amount:.6f}",
            approved_order.to_dict(),
        )

        try:
            if approved_order.order_type == "market":
                raw_order = await self.exchange.create_market_order(
                    symbol=symbol,
                    side=approved_order.side,
                    amount=approved_order.amount,
                )
            elif approved_order.order_type == "orderbook":
                # 매수=bid(유리), 매도=ask(유리). 손절/긴급청산만 별도로 bid 매도.
                raw_order = await self.exchange.create_orderbook_limit_order(
                    symbol=symbol,
                    side=approved_order.side,
                    amount=approved_order.amount,
                    aggressive=False,
                )
            else:
                if approved_order.price is None:
                    raise ValueError("지정가 주문에 가격이 없습니다.")
                raw_order = await self.exchange.create_limit_order(
                    symbol=symbol,
                    side=approved_order.side,
                    amount=approved_order.amount,
                    price=approved_order.price,
                )

            # 체결 결과 파싱
            filled_price = raw_order.get("price") or raw_order.get("average") or approved_order.trading_signal.market_signal.price
            filled_amount = raw_order.get("filled") or approved_order.amount
            cost = raw_order.get("cost") or (filled_amount * filled_price)
            fee_data = raw_order.get("fee", {})
            fee = fee_data.get("cost", 0.0) if isinstance(fee_data, dict) else 0.0

            realized_pnl = None
            if approved_order.side == "sell" and symbol in self.active_positions:
                pos = self.active_positions[symbol]
                entry = float(pos.get("entry_price") or 0)
                realized_pnl = (filled_price - entry) * filled_amount - fee

            trade_result = TradeResult(
                trade_id=str(raw_order.get("id") or uuid.uuid4()),
                approved_order=approved_order,
                status="filled",
                filled_amount=filled_amount,
                filled_price=filled_price,
                cost=cost,
                fee=fee,
                is_paper=self.exchange.paper_trading,
                realized_pnl=realized_pnl,
            )

            # 포지션 업데이트
            if approved_order.side == "buy":
                self.active_positions[symbol] = {
                    "symbol": symbol,
                    "side": "long",
                    "amount": filled_amount,
                    "entry_price": filled_price,
                    "stop_loss": approved_order.stop_loss,
                    "take_profit": approved_order.take_profit,
                    "trade_id": trade_result.trade_id,
                    "opened_at": datetime.utcnow().isoformat(),
                }
                if self.on_position_update:
                    await self.on_position_update(symbol, self.active_positions[symbol])

            elif approved_order.side == "sell" and symbol in self.active_positions:
                del self.active_positions[symbol]
                if self.on_position_update:
                    await self.on_position_update(symbol, None)

            await self._log(
                "DECISION",
                f"{symbol} 주문 체결: {approved_order.side} {filled_amount:.6f} @ {filled_price:.2f}",
                trade_result.to_dict(),
            )

            # PortfolioAgent에 결과 전달
            if self.on_trade_result:
                await self.on_trade_result(trade_result)

            return trade_result

        except Exception as e:
            trade_result = TradeResult(
                trade_id=str(uuid.uuid4()),
                approved_order=approved_order,
                status="failed",
                filled_amount=0.0,
                filled_price=0.0,
                cost=0.0,
                fee=0.0,
                is_paper=self.exchange.paper_trading,
                error=str(e),
            )

            await self._log("ERROR", f"{symbol} 주문 실패: {e}", {"error": str(e)})

            if self.on_trade_result:
                await self.on_trade_result(trade_result)

            return trade_result

    async def _check_stop_loss_take_profit(self, symbol: str, position: dict):
        """손절/익절 조건 확인 및 실행"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            current_price = ticker["last"]

            entry_price = position["entry_price"]
            stop_loss = position["stop_loss"]
            take_profit = position["take_profit"]

            should_close = False
            close_reason = ""

            if current_price <= stop_loss:
                should_close = True
                close_reason = f"손절 발동 ({current_price:.2f} ≤ {stop_loss:.2f})"
            elif current_price >= take_profit:
                should_close = True
                close_reason = f"익절 발동 ({current_price:.2f} ≥ {take_profit:.2f})"

            if should_close:
                await self._log("DECISION", f"{symbol} 포지션 청산: {close_reason}")

                if settings.ORDER_EXECUTION_MODE == "market":
                    raw_order = await self.exchange.create_market_order(
                        symbol=symbol, side="sell", amount=position["amount"]
                    )
                    fill_amt = float(raw_order.get("filled") or position["amount"])
                    fill_px = float(
                        raw_order.get("average")
                        or raw_order.get("price")
                        or current_price
                    )
                else:
                    raw_order = await self.exchange.create_orderbook_limit_order(
                        symbol=symbol,
                        side="sell",
                        amount=position["amount"],
                        aggressive=True,
                    )
                    fill_amt = float(raw_order.get("filled") or position["amount"])
                    fill_px = float(raw_order.get("average") or raw_order.get("price") or current_price)

                pnl = (fill_px - entry_price) * fill_amt
                await self._log(
                    "INFO",
                    f"{symbol} 청산 완료: PnL={pnl:+.2f} USD",
                    {"pnl": pnl, "reason": close_reason},
                )

                del self.active_positions[symbol]
                if self.on_position_update:
                    await self.on_position_update(symbol, None)

        except Exception as e:
            await self._log("ERROR", f"{symbol} 손절/익절 체크 오류: {e}")

    async def close_all_positions(self):
        """모든 포지션 긴급 청산"""
        await self._log("WARNING", "전체 포지션 긴급 청산 시작")

        for symbol, position in list(self.active_positions.items()):
            try:
                if settings.ORDER_EXECUTION_MODE == "market":
                    await self.exchange.create_market_order(
                        symbol=symbol, side="sell", amount=position["amount"]
                    )
                else:
                    await self.exchange.create_orderbook_limit_order(
                        symbol=symbol,
                        side="sell",
                        amount=position["amount"],
                        aggressive=True,
                    )
                del self.active_positions[symbol]
                await self._log("INFO", f"{symbol} 긴급 청산 완료")
            except Exception as e:
                await self._log("ERROR", f"{symbol} 긴급 청산 실패: {e}")

        await self._log("WARNING", "전체 포지션 긴급 청산 완료")
