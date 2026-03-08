"""
PortfolioAgent - 포트폴리오 성과 추적 에이전트
거래 결과를 집계하고 실시간 포트폴리오 현황을 관리합니다.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from loguru import logger

from agents.base_agent import BaseAgent
from agents.execution_agent import TradeResult
from exchange.connector import ExchangeConnector
from core.config import settings


@dataclass
class PortfolioState:
    """실시간 포트폴리오 상태"""
    total_value_usd: float = 0.0
    cash_usd: float = 0.0
    positions: Dict[str, dict] = field(default_factory=dict)
    pnl_today: float = 0.0
    pnl_total: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    initial_balance: float = 0.0
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def win_rate(self) -> float:
        """승률 계산"""
        closed = self.winning_trades + self.losing_trades
        return (self.winning_trades / closed * 100) if closed > 0 else 0.0

    @property
    def total_return_pct(self) -> float:
        """총 수익률"""
        if self.initial_balance <= 0:
            return 0.0
        return (self.total_value_usd - self.initial_balance) / self.initial_balance * 100

    def to_dict(self) -> dict:
        return {
            "total_value_usd": round(self.total_value_usd, 2),
            "cash_usd": round(self.cash_usd, 2),
            "positions": self.positions,
            "pnl_today": round(self.pnl_today, 2),
            "pnl_total": round(self.pnl_total, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 1),
            "total_return_pct": round(self.total_return_pct, 2),
            "initial_balance": round(self.initial_balance, 2),
            "updated_at": self.updated_at.isoformat(),
        }


class PortfolioAgent(BaseAgent):
    """
    포트폴리오 에이전트
    
    역할:
    - 실시간 포트폴리오 가치 계산
    - 거래 결과 집계 (승률, PnL)
    - DB에 포트폴리오 스냅샷 저장
    - WebSocket으로 실시간 대시보드 업데이트
    """

    agent_type = "portfolio"

    def __init__(
        self,
        exchange: ExchangeConnector,
        on_update: Optional[Callable[[PortfolioState], None]] = None,
        initial_balance: Optional[float] = None,
    ):
        super().__init__()
        self.exchange = exchange
        self.on_update = on_update

        # 초기 잔고 설정
        _initial = initial_balance or settings.PAPER_TRADING_BALANCE
        self.portfolio = PortfolioState(
            total_value_usd=_initial,
            cash_usd=_initial,
            initial_balance=_initial,
        )

        # DB 저장 콜백
        self._db_save_callback = None

    def set_db_callback(self, callback):
        """DB 저장 콜백 설정"""
        self._db_save_callback = callback

    async def run_cycle(self):
        """포트폴리오 상태 업데이트"""
        await self._update_portfolio()

        # DB 스냅샷 저장
        if self._db_save_callback:
            try:
                await self._db_save_callback(self.portfolio)
            except Exception as e:
                await self._log("ERROR", f"포트폴리오 DB 저장 실패: {e}")

        # WebSocket으로 업데이트 전송
        if self.on_update:
            await self.on_update(self.portfolio)

    async def on_trade_result(self, result: TradeResult):
        """거래 체결 결과 처리"""
        self.portfolio.total_trades += 1

        if result.status == "filled":
            if result.approved_order.side == "buy":
                # 매수: 현금 감소
                self.portfolio.cash_usd -= result.cost + result.fee
                self.portfolio.positions[result.approved_order.symbol] = {
                    "symbol": result.approved_order.symbol,
                    "amount": result.filled_amount,
                    "entry_price": result.filled_price,
                    "current_price": result.filled_price,
                    "unrealized_pnl": 0.0,
                    "stop_loss": result.approved_order.stop_loss,
                    "take_profit": result.approved_order.take_profit,
                }

            elif result.approved_order.side == "sell":
                symbol = result.approved_order.symbol
                # 매도: 현금 증가 + PnL 계산
                self.portfolio.cash_usd += result.cost - result.fee

                if symbol in self.portfolio.positions:
                    entry_price = self.portfolio.positions[symbol]["entry_price"]
                    amount = self.portfolio.positions[symbol]["amount"]
                    pnl = (result.filled_price - entry_price) * amount - result.fee

                    self.portfolio.pnl_total += pnl
                    self.portfolio.pnl_today += pnl

                    if pnl >= 0:
                        self.portfolio.winning_trades += 1
                    else:
                        self.portfolio.losing_trades += 1

                    del self.portfolio.positions[symbol]

                    await self._log(
                        "INFO",
                        f"거래 완료: {symbol} PnL={pnl:+.2f} USD (총 PnL={self.portfolio.pnl_total:+.2f})",
                    )

        # 즉시 업데이트
        await self._update_portfolio()
        if self.on_update:
            await self.on_update(self.portfolio)

    async def _update_portfolio(self):
        """포트폴리오 총 가치 계산"""
        try:
            total_position_value = 0.0

            # 각 포지션의 현재 가치 계산
            for symbol, position in self.portfolio.positions.items():
                try:
                    ticker = await self.exchange.fetch_ticker(symbol)
                    current_price = ticker["last"]
                    position["current_price"] = current_price

                    position_value = position["amount"] * current_price
                    total_position_value += position_value

                    # 미실현 손익 계산
                    entry_price = position["entry_price"]
                    unrealized_pnl = (current_price - entry_price) * position["amount"]
                    position["unrealized_pnl"] = round(unrealized_pnl, 2)

                except Exception as e:
                    logger.warning(f"{symbol} 가격 조회 실패: {e}")

            self.portfolio.total_value_usd = self.portfolio.cash_usd + total_position_value
            self.portfolio.updated_at = datetime.utcnow()

        except Exception as e:
            await self._log("ERROR", f"포트폴리오 업데이트 오류: {e}")

    def get_summary(self) -> dict:
        """포트폴리오 요약 정보"""
        return self.portfolio.to_dict()
