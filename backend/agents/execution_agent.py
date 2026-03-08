"""
ExecutionAgent - 실제 주문 실행 에이전트
ApprovedOrder를 받아 거래소에 주문을 실행합니다.
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Optional

from loguru import logger

from agents.base_agent import BaseAgent
from agents.risk_manager import ApprovedOrder
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

    def to_dict(self) -> dict:
        return {
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
    ):
        super().__init__()
        self.exchange = exchange
        self.on_trade_result = on_trade_result
        self.on_position_update = on_position_update

        # 활성 포지션 추적
        self.active_positions: Dict[str, dict] = {}

    async def run_cycle(self):
        """활성 포지션 손절/익절 체크"""
        if not self.active_positions:
            return

        await self._log("INFO", f"포지션 모니터링: {len(self.active_positions)}개")

        for symbol, position in list(self.active_positions.items()):
            try:
                await self._check_stop_loss_take_profit(symbol, position)
            except Exception as e:
                await self._log("ERROR", f"{symbol} 포지션 체크 오류: {e}")

    async def execute_order(self, approved_order: ApprovedOrder):
        """승인된 주문 실행"""
        symbol = approved_order.symbol

        await self._log(
            "INFO",
            f"{symbol} 주문 실행 시작: {approved_order.side} {approved_order.amount:.6f}",
            approved_order.to_dict(),
        )

        try:
            # 거래소에 주문 실행
            if approved_order.order_type == "market":
                raw_order = await self.exchange.create_market_order(
                    symbol=symbol,
                    side=approved_order.side,
                    amount=approved_order.amount,
                )
            else:
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

            trade_result = TradeResult(
                trade_id=raw_order.get("id", str(uuid.uuid4())),
                approved_order=approved_order,
                status="filled",
                filled_amount=filled_amount,
                filled_price=filled_price,
                cost=cost,
                fee=fee,
                is_paper=self.exchange.paper_trading,
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

                # 청산 주문 실행
                raw_order = await self.exchange.create_market_order(
                    symbol=symbol,
                    side="sell",
                    amount=position["amount"],
                )

                pnl = (current_price - entry_price) * position["amount"]
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
                await self.exchange.create_market_order(
                    symbol=symbol,
                    side="sell",
                    amount=position["amount"],
                )
                del self.active_positions[symbol]
                await self._log("INFO", f"{symbol} 긴급 청산 완료")
            except Exception as e:
                await self._log("ERROR", f"{symbol} 긴급 청산 실패: {e}")

        await self._log("WARNING", "전체 포지션 긴급 청산 완료")
