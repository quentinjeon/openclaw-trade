"""
RiskManagerAgent - 리스크 평가 및 포지션 크기 결정 에이전트
TradingSignal을 검토하고 리스크 기준에 맞는 주문만 승인합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Callable, Dict, List, Optional

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
    order_type: str         # market | limit
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

        logger.info(
            f"리스크 관리 에이전트 초기화: "
            f"최대포지션={self.max_position_size_pct}%, "
            f"최대동시포지션={self.max_open_positions}개, "
            f"일일손실한도={self.daily_loss_limit_pct}%"
        )

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
        self.total_portfolio_usd = current_balance

        # 리스크 체크 목록
        rejection_reason = self._check_risks(signal, current_balance)

        if rejection_reason:
            rejected = RejectedSignal(trading_signal=signal, reason=rejection_reason)
            await self._log(
                "WARNING",
                f"{signal.symbol} 신호 거부: {rejection_reason}",
                signal.to_dict(),
            )
            return rejected

        # 포지션 크기 계산
        position_size_pct, amount = self._calculate_position_size(
            signal, current_balance
        )

        # 손절/익절가 계산
        price = signal.market_signal.price
        if signal.action == "BUY":
            stop_loss = price * (1 - self.stop_loss_pct / 100)
            take_profit = price * (1 + self.take_profit_pct / 100)
        else:  # SELL
            stop_loss = price * (1 + self.stop_loss_pct / 100)
            take_profit = price * (1 - self.take_profit_pct / 100)

        approved = ApprovedOrder(
            trading_signal=signal,
            symbol=signal.symbol,
            exchange=signal.exchange,
            side="buy" if signal.action == "BUY" else "sell",
            amount=amount,
            order_type="market",
            price=None,  # 시장가
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            position_size_pct=position_size_pct,
        )

        await self._log(
            "DECISION",
            f"{signal.symbol} 주문 승인: {approved.side} {approved.amount:.6f} @ 시장가",
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

        # 4. 일일 손실 한도 확인
        daily_loss_limit_usd = self.total_portfolio_usd * self.daily_loss_limit_pct / 100
        if self.daily_loss_usd >= daily_loss_limit_usd:
            return (
                f"일일 손실 한도 초과: "
                f"손실={self.daily_loss_usd:.2f} USD, "
                f"한도={daily_loss_limit_usd:.2f} USD"
            )

        # 5. 잔고 최소 기준 ($10 이상)
        if balance < 10:
            return f"잔고 부족: {balance:.2f} USD < 10 USD"

        return None  # 모든 체크 통과

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

        position_size_pct = self.max_position_size_pct * size_multiplier
        position_usd = balance * position_size_pct / 100

        # 현재 가격으로 수량 계산
        price = signal.market_signal.price
        if price <= 0:
            return 0.0, 0.0

        amount = position_usd / price

        return round(position_size_pct, 2), round(amount, 8)

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
