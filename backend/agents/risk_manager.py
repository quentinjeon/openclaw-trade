"""
RiskManagerAgent - 리스크 평가 및 포지션 크기 결정 에이전트
TradingSignal을 검토하고 리스크 기준에 맞는 주문만 승인합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from agents.base_agent import BaseAgent
from agents.strategy_agent import TradingSignal
from core.config import settings


@dataclass
class ApprovedOrder:
    """리스크 검증을 통과한 승인된 주문"""
    trading_signal: TradingSignal
    symbol: str
    exchange: str
    side: str               # buy | sell
    amount: float           # 주문 수량
    order_type: str         # market | orderbook | limit (+ 명시 price)
    price: Optional[float]  # None = 시장가
    stop_loss: float        # 손절가
    take_profit: float      # 익절가
    position_size_pct: float  # 포지션 크기 (계좌의 %)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side,
            "amount": self.amount,
            "order_type": self.order_type,
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size_pct": self.position_size_pct,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RejectedSignal:
    """리스크 검증 실패"""
    trading_signal: TradingSignal
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RiskManagerAgent(BaseAgent):
    """
    리스크 관리 에이전트
    
    역할:
    - 포지션 크기 자동 계산 (Kelly Criterion 기반)
    - 최대 포지션 수 제한
    - 일일 손실 한도 확인
    - 손절/익절가 자동 설정
    - 승인된 주문을 ExecutionAgent에 전달
    """

    agent_type = "risk_manager"

    def __init__(
        self,
        on_approve: Optional[Callable[[ApprovedOrder], None]] = None,
        max_position_size_pct: Optional[float] = None,
        max_open_positions: Optional[int] = None,
        daily_loss_limit_pct: Optional[float] = None,
    ):
        super().__init__()
        self.on_approve = on_approve

        # 리스크 파라미터
        self.max_position_size_pct = max_position_size_pct or settings.MAX_POSITION_SIZE_PCT
        self.max_open_positions = max_open_positions or settings.MAX_OPEN_POSITIONS
        self.daily_loss_limit_pct = daily_loss_limit_pct or settings.DAILY_LOSS_LIMIT_PCT
        self.stop_loss_pct = settings.DEFAULT_STOP_LOSS_PCT
        self.take_profit_pct = settings.DEFAULT_TAKE_PROFIT_PCT

        # 상태 추적
        self.open_positions: Dict[str, dict] = {}   # symbol -> position info
        self.daily_loss_usd: float = 0.0
        self.last_reset_date: date = date.today()
        self.total_portfolio_usd: float = settings.PAPER_TRADING_BALANCE
        self._connector: Optional[Any] = None  # ExchangeConnector (실거래 시 free 쿼트·limits)

        logger.info(
            f"리스크 관리 에이전트 초기화: "
            f"최대포지션={self.max_position_size_pct}%, "
            f"최대동시포지션={self.max_open_positions}개, "
            f"일일손실한도={self.daily_loss_limit_pct}%"
        )

    def set_connector(self, connector: Optional[Any]) -> None:
        """실거래 시 매수 예산·최소 명목가 계산에 거래소 연결 사용."""
        self._connector = connector

    async def run_cycle(self):
        """리스크 상태 주기적 확인"""
        # 일일 손실 카운터 리셋 (날짜 변경 시)
        today = date.today()
        if today != self.last_reset_date:
            self.daily_loss_usd = 0.0
            self.last_reset_date = today
            await self._log("INFO", "일일 손실 카운터 리셋")

    async def evaluate_signal(self, signal: TradingSignal, current_balance: float):
        """
        매매 신호 리스크 평가
        
        Args:
            signal: StrategyAgent의 TradingSignal
            current_balance: 현재 USDT 잔고
        """
        # 매수: 거래소 해당 쿼트(USDT 등) free 잔고 기준 — 포트폴리오 추정치와 불일치해도 실주문 가능액만 사용
        balance_for_risk = current_balance
        if signal.action == "BUY":
            fq = await self._fetch_free_quote_balance(signal)
            if fq is not None:
                balance_for_risk = fq
        self.total_portfolio_usd = balance_for_risk

        rejection_reason = self._check_risks(signal, balance_for_risk)

        if rejection_reason:
            rejected = RejectedSignal(trading_signal=signal, reason=rejection_reason)
            await self._log(
                "WARNING",
                f"{signal.symbol} 신호 거부: {rejection_reason}",
                signal.to_dict(),
            )
            return rejected

        if signal.action == "BUY":
            position_size_pct, amount, buy_reject = await self._finalize_buy_size(
                signal, balance_for_risk
            )
            if buy_reject:
                rej = RejectedSignal(trading_signal=signal, reason=buy_reject)
                await self._log("WARNING", f"{signal.symbol} 매수 거부: {buy_reject}", signal.to_dict())
                return rej
        else:
            position_size_pct, amount = self._calculate_position_size(
                signal, current_balance
            )

        if signal.action == "SELL" and amount <= 0:
            rej = RejectedSignal(
                trading_signal=signal,
                reason="청산 수량 없음 (포지션 수량 0 또는 미추적)",
            )
            await self._log("WARNING", rej.reason, signal.to_dict())
            return rej

        if signal.action == "BUY" and amount <= 0:
            rej = RejectedSignal(
                trading_signal=signal,
                reason="매수 수량 0 (가용 쿼트·최소 명목가·정밀도)",
            )
            await self._log("WARNING", rej.reason, signal.to_dict())
            return rej

        # 손절/익절가 계산
        price = signal.market_signal.price
        if signal.action == "BUY":
            stop_loss = price * (1 - self.stop_loss_pct / 100)
            take_profit = price * (1 + self.take_profit_pct / 100)
        else:  # SELL
            stop_loss = price * (1 + self.stop_loss_pct / 100)
            take_profit = price * (1 - self.take_profit_pct / 100)

        _mode = getattr(settings, "ORDER_EXECUTION_MODE", "orderbook") or "orderbook"
        _ot = "market" if _mode == "market" else "orderbook"
        approved = ApprovedOrder(
            trading_signal=signal,
            symbol=signal.symbol,
            exchange=signal.exchange,
            side="buy" if signal.action == "BUY" else "sell",
            amount=amount,
            order_type=_ot,
            price=None,
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            position_size_pct=position_size_pct,
        )

        _px_label = "시장가" if _ot == "market" else "호가 최유리 지정가(bid/ask)"
        await self._log(
            "DECISION",
            f"{signal.symbol} 주문 승인: {approved.side} {approved.amount:.6f} @ {_px_label}",
            approved.to_dict(),
        )

        # ExecutionAgent로 전달
        if self.on_approve:
            await self.on_approve(approved)

        return approved

    def _check_risks(self, signal: TradingSignal, balance: float) -> Optional[str]:
        """리스크 조건 확인, 거부 이유 반환 (None이면 승인)"""

        # 1. 신뢰도 최소 기준 (50% 이상)
        if signal.confidence < 0.5:
            return f"신뢰도 부족: {signal.confidence:.1%} < 50%"

        # 2. 최대 동시 포지션 수 확인
        if signal.action == "BUY" and len(self.open_positions) >= self.max_open_positions:
            return f"최대 포지션 수 초과: {len(self.open_positions)}/{self.max_open_positions}"

        # 3. 동일 심볼 중복 포지션 방지
        if signal.symbol in self.open_positions and signal.action == "BUY":
            return f"이미 {signal.symbol} 포지션 보유 중"

        # 4. 일일 손실 한도 — 신규 매수만 제한 (청산 매도는 포지션 해제 허용)
        daily_loss_limit_usd = self.total_portfolio_usd * self.daily_loss_limit_pct / 100
        if (
            signal.action == "BUY"
            and self.daily_loss_usd >= daily_loss_limit_usd
        ):
            return (
                f"일일 손실 한도 초과: "
                f"손실={self.daily_loss_usd:.2f} USD, "
                f"한도={daily_loss_limit_usd:.2f} USD"
            )

        # 5. 잔고 최소 기준 ($10 이상) — 매도 청산은 USDT 잔고와 무관
        if signal.action == "BUY" and balance < 10:
            return f"잔고 부족: {balance:.2f} USD < 10 USD"

        # 6. 매도는 반드시 보유 포지션과 수량 일치
        if signal.action == "SELL":
            pos = self.open_positions.get(signal.symbol)
            if not pos:
                return f"{signal.symbol} 청산 불가: 추적 중인 포지션 없음"

        return None  # 모든 체크 통과

    async def _fetch_free_quote_balance(self, signal: TradingSignal) -> Optional[float]:
        """심볼 쿼트 통화(예: BTC/USDT → USDT) 거래소 free 잔고. 실패·페이퍼 시 None."""
        c = self._connector
        if not c or getattr(c, "paper_trading", True):
            return None
        ex = getattr(c, "_exchange", None)
        if not ex:
            return None
        try:
            bal = await ex.fetch_balance()
            quote = signal.symbol.split("/")[1] if "/" in signal.symbol else "USDT"
            row = bal.get(quote) or {}
            return float(row.get("free") or 0)
        except Exception as e:
            logger.warning(f"{signal.symbol} free 쿼트 조회 실패, 포트폴리오 추정 사용: {e}")
            return None

    def _market_cost_min_usd(self, symbol: str) -> float:
        floor = float(getattr(settings, "ORDER_MIN_NOTIONAL_FALLBACK_USD", 5.0) or 5.0)
        c = self._connector
        ex = getattr(c, "_exchange", None) if c and not getattr(c, "paper_trading", True) else None
        if not ex:
            return floor
        try:
            m = ex.market(symbol)
            cost = (m.get("limits") or {}).get("cost") or {}
            mn = cost.get("min")
            if mn is not None and float(mn) > 0:
                return float(mn)
        except Exception:
            pass
        return floor

    def _amount_meeting_min_notional(
        self,
        ex: Any,
        symbol: str,
        price: float,
        target_usd: float,
        cost_min: float,
        usable_usd: float,
    ) -> Optional[float]:
        """정밀도 반영 후 명목가 ≥ cost_min 이고 ≤ usable_usd 인 수량."""

        def try_amt(quote_usd: float) -> Optional[float]:
            if quote_usd < cost_min * 0.99 or quote_usd > usable_usd * 1.01:
                return None
            a = float(ex.amount_to_precision(symbol, quote_usd / price))
            if a <= 0:
                return None
            n = a * price
            if n >= cost_min * 0.998 and n <= usable_usd * 1.003:
                return a
            return None

        if price <= 0:
            return None
        for q in (target_usd, usable_usd, min(usable_usd, max(target_usd, cost_min))):
            hit = try_amt(q)
            if hit is not None:
                return hit
        amt = (cost_min / price) * 1.02
        cap_amt = (usable_usd / price) * 1.01
        for _ in range(250):
            if amt > cap_amt:
                break
            a = float(ex.amount_to_precision(symbol, amt))
            if a > 0:
                n = a * price
                if n >= cost_min * 0.998:
                    if n <= usable_usd * 1.003:
                        return a
                    break
            amt *= 1.002
        return None

    async def _finalize_buy_size(
        self, signal: TradingSignal, free_quote: float
    ) -> tuple[float, float, Optional[str]]:
        """
        가용 쿼트·최소 명목가·수량 step 반영 매수 규모.
        Returns: (position_size_pct, amount, reject_reason)
        """
        price = signal.market_signal.price
        if price <= 0:
            return 0.0, 0.0, "가격 없음"

        reserve_pct = float(getattr(settings, "CASH_FEE_RESERVE_PCT", 0.35) or 0) / 100.0
        usable = max(0.0, free_quote * (1.0 - reserve_pct))
        quote_ccy = signal.symbol.split("/")[1] if "/" in signal.symbol else "USDT"
        cost_min = self._market_cost_min_usd(signal.symbol)

        size_multiplier = signal.confidence * 2 - 0.5
        size_multiplier = max(0.3, min(1.0, size_multiplier))
        position_size_pct = self.max_position_size_pct * size_multiplier
        raw_mult = signal.indicators.get("_score_alloc_mult")
        sm = 1.0
        if raw_mult is not None:
            sm = max(0.12, min(1.0, float(raw_mult)))

        target_usd = usable * (position_size_pct / 100.0) * sm
        target_usd = min(target_usd, usable * (self.max_position_size_pct / 100.0))
        eff_pct = min(position_size_pct * sm, self.max_position_size_pct)

        if usable < cost_min:
            return (
                0.0,
                0.0,
                f"가용 {quote_ccy} 부족: 수수료 예약 후 {usable:.2f} < 최소 명목가 약 {cost_min:.2f}",
            )

        if target_usd < cost_min:
            target_usd = cost_min
        target_usd = min(target_usd, usable)

        ex = getattr(self._connector, "_exchange", None) if self._connector else None
        paper = not ex or getattr(self._connector, "paper_trading", True)

        if paper:
            amount = target_usd / price
            return round(eff_pct, 2), round(amount, 8), None

        amount = self._amount_meeting_min_notional(
            ex, signal.symbol, price, target_usd, cost_min, usable
        )
        if amount is None or amount <= 0:
            return (
                0.0,
                0.0,
                f"최소 명목가({cost_min:.2f})·정밀도를 가용 {usable:.2f} {quote_ccy} 안에서 맞출 수 없음",
            )
        est = amount * price
        if est > usable * 1.003:
            return (
                0.0,
                0.0,
                f"주문 명목가 {est:.2f} {quote_ccy} > 가용 {usable:.2f} (반올림 후 초과)",
            )
        return round(eff_pct, 2), amount, None

    def _calculate_position_size(
        self, signal: TradingSignal, balance: float
    ) -> tuple[float, float]:
        """
        포지션 크기 계산
        
        기본: 최대 포지션 크기 % 사용
        신뢰도가 높을수록 포지션 크기 증가 (최대 한도 내에서)
        
        Returns:
            (position_size_pct, amount)
        """
        # 신뢰도 기반 포지션 크기 조정
        # 신뢰도 0.5 → 50% 크기, 신뢰도 1.0 → 100% 크기
        size_multiplier = signal.confidence * 2 - 0.5  # 0.5~1.5 범위
        size_multiplier = max(0.3, min(1.0, size_multiplier))  # 0.3~1.0으로 제한

        if signal.action == "SELL":
            pos = self.open_positions.get(signal.symbol)
            if not pos:
                return 0.0, 0.0
            amt = float(pos.get("amount") or 0)
            if amt <= 0:
                return 0.0, 0.0
            return 0.0, round(amt, 8)

        position_size_pct = self.max_position_size_pct * size_multiplier
        position_usd = balance * position_size_pct / 100

        raw_mult = signal.indicators.get("_score_alloc_mult")
        sm = 1.0
        if raw_mult is not None:
            sm = max(0.12, min(1.0, float(raw_mult)))
            position_usd *= sm

        price = signal.market_signal.price
        if price <= 0:
            return 0.0, 0.0

        amount = position_usd / price
        eff_pct = min(position_size_pct * sm, self.max_position_size_pct)
        return round(eff_pct, 2), round(amount, 8)

    def update_position(self, symbol: str, position_data: Optional[dict]):
        """포지션 정보 업데이트 (ExecutionAgent에서 호출)"""
        if position_data:
            self.open_positions[symbol] = position_data
        else:
            self.open_positions.pop(symbol, None)

    def record_loss(self, loss_usd: float):
        """손실 기록 (ExecutionAgent에서 호출)"""
        if loss_usd > 0:  # 손실만 기록
            self.daily_loss_usd += loss_usd

    def update_risk_params(self, params: dict):
        """리스크 파라미터 업데이트"""
        if "max_position_size_pct" in params:
            self.max_position_size_pct = float(params["max_position_size_pct"])
        if "max_open_positions" in params:
            self.max_open_positions = int(params["max_open_positions"])
        if "daily_loss_limit_pct" in params:
            self.daily_loss_limit_pct = float(params["daily_loss_limit_pct"])
        if "stop_loss_pct" in params:
            self.stop_loss_pct = float(params["stop_loss_pct"])
        if "take_profit_pct" in params:
            self.take_profit_pct = float(params["take_profit_pct"])

        logger.info(f"리스크 파라미터 업데이트: {params}")
