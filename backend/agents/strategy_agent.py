"""
StrategyAgent - 매매 전략 실행 에이전트
MarketSignal을 받아 활성화된 전략으로 TradingSignal을 생성합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

import pandas as pd
from loguru import logger

from agents.base_agent import BaseAgent
from agents.market_analyzer import MarketSignal
from exchange.connector import ExchangeConnector
from strategies import AVAILABLE_STRATEGIES
from strategies.base_strategy import BaseStrategy, StrategySignal


@dataclass
class TradingSignal:
    """매매 실행 신호"""
    symbol: str
    exchange: str
    action: str             # BUY | SELL | HOLD
    strategy_name: str
    confidence: float
    reasoning: str
    market_signal: MarketSignal
    indicators: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "action": self.action,
            "strategy_name": self.strategy_name,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "indicators": self.indicators,
            "market_signal": self.market_signal.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }


class StrategyAgent(BaseAgent):
    """
    전략 에이전트
    
    역할:
    - MarketSignal 수신 및 전략 실행
    - 활성화된 전략(RSI, MACD, 볼린저)으로 매매 신호 생성
    - 다중 전략 합산으로 최종 TradingSignal 생성
    - TradingSignal을 RiskManagerAgent에 전달
    """

    agent_type = "strategy"

    def __init__(
        self,
        exchange: ExchangeConnector,
        active_strategies: Optional[List[str]] = None,
        on_signal: Optional[Callable[[TradingSignal], None]] = None,
    ):
        super().__init__()
        self.exchange = exchange
        self.on_signal = on_signal

        # 활성화된 전략 초기화
        self.strategies: Dict[str, BaseStrategy] = {}
        active = active_strategies or list(AVAILABLE_STRATEGIES.keys())
        for strategy_name in active:
            if strategy_name in AVAILABLE_STRATEGIES:
                self.strategies[strategy_name] = AVAILABLE_STRATEGIES[strategy_name]()

        # 대기 중인 시장 신호
        self._pending_signals: List[MarketSignal] = []

        logger.info(f"전략 에이전트 초기화: 활성 전략={list(self.strategies.keys())}")

    async def on_market_signal(self, signal: MarketSignal):
        """MarketAnalyzerAgent로부터 신호 수신"""
        self._pending_signals.append(signal)
        # 즉시 처리
        await self._process_signal(signal)

    async def run_cycle(self):
        """대기 중인 신호 처리 (주기적 실행)"""
        if self._pending_signals:
            await self._log("INFO", f"대기 신호 {len(self._pending_signals)}개 처리")

    async def _process_signal(self, market_signal: MarketSignal):
        """시장 신호를 받아 전략 실행"""
        symbol = market_signal.symbol

        await self._log(
            "INFO",
            f"{symbol} 전략 실행: 시장={market_signal.direction}",
        )

        # OHLCV 데이터 조회
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe="1h", limit=200)
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("timestamp")
        except Exception as e:
            await self._log("ERROR", f"{symbol} OHLCV 조회 실패: {e}")
            return

        # 각 전략 실행
        signals: List[StrategySignal] = []
        for strategy_name, strategy in self.strategies.items():
            if strategy.enabled:
                try:
                    sig = strategy.generate_signal(df)
                    signals.append(sig)
                    await self._log(
                        "INFO",
                        f"{symbol} [{strategy_name}]: {sig.action} (신뢰도={sig.confidence:.2%})",
                        {"strategy": strategy_name, "signal": sig.action, "confidence": sig.confidence},
                    )
                except Exception as e:
                    await self._log("ERROR", f"{symbol} [{strategy_name}] 전략 오류: {e}")

        if not signals:
            return

        # 전략 신호 합산
        trading_signal = self._aggregate_signals(symbol, market_signal, signals)

        await self._log(
            "DECISION",
            f"{symbol} 최종 신호: {trading_signal.action} (신뢰도={trading_signal.confidence:.2%})",
            trading_signal.to_dict(),
        )

        # RiskManagerAgent로 전달
        if trading_signal.action != "HOLD" and self.on_signal:
            await self.on_signal(trading_signal)

    def _aggregate_signals(
        self,
        symbol: str,
        market_signal: MarketSignal,
        strategy_signals: List[StrategySignal],
    ) -> TradingSignal:
        """다중 전략 신호 합산"""
        buy_score = 0.0
        sell_score = 0.0

        for sig in strategy_signals:
            if sig.action == "BUY":
                buy_score += sig.confidence
            elif sig.action == "SELL":
                sell_score += sig.confidence

        total = buy_score + sell_score
        if total == 0:
            return TradingSignal(
                symbol=symbol,
                exchange=market_signal.exchange,
                action="HOLD",
                strategy_name="combined",
                confidence=0.5,
                reasoning="모든 전략 HOLD",
                market_signal=market_signal,
            )

        buy_ratio = buy_score / total
        sell_ratio = sell_score / total

        # 60% 이상 동의 시 신호 생성
        if buy_ratio >= 0.6 and market_signal.direction in ("BULLISH", "NEUTRAL"):
            confidence = (buy_score / len(strategy_signals)) * (1 + market_signal.confidence) / 2
            reasoning_parts = [
                f"{s.strategy_name}: {s.reasoning}"
                for s in strategy_signals if s.action == "BUY"
            ]
            return TradingSignal(
                symbol=symbol,
                exchange=market_signal.exchange,
                action="BUY",
                strategy_name="combined",
                confidence=min(confidence, 1.0),
                reasoning=" | ".join(reasoning_parts),
                market_signal=market_signal,
                indicators={s.strategy_name: s.indicators for s in strategy_signals},
            )

        elif sell_ratio >= 0.6 and market_signal.direction in ("BEARISH", "NEUTRAL"):
            confidence = (sell_score / len(strategy_signals)) * (1 + market_signal.confidence) / 2
            reasoning_parts = [
                f"{s.strategy_name}: {s.reasoning}"
                for s in strategy_signals if s.action == "SELL"
            ]
            return TradingSignal(
                symbol=symbol,
                exchange=market_signal.exchange,
                action="SELL",
                strategy_name="combined",
                confidence=min(confidence, 1.0),
                reasoning=" | ".join(reasoning_parts),
                market_signal=market_signal,
                indicators={s.strategy_name: s.indicators for s in strategy_signals},
            )

        else:
            return TradingSignal(
                symbol=symbol,
                exchange=market_signal.exchange,
                action="HOLD",
                strategy_name="combined",
                confidence=0.5,
                reasoning=f"전략 합의 부족: BUY={buy_ratio:.1%}, SELL={sell_ratio:.1%}",
                market_signal=market_signal,
            )

    def update_strategy_params(self, strategy_name: str, params: dict):
        """전략 파라미터 업데이트"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].update_params(params)
            logger.info(f"전략 파라미터 업데이트: {strategy_name} = {params}")

    def toggle_strategy(self, strategy_name: str, enabled: bool):
        """전략 활성화/비활성화"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = enabled
            logger.info(f"전략 {'활성화' if enabled else '비활성화'}: {strategy_name}")
