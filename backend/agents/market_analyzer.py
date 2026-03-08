"""
MarketAnalyzerAgent - 시장 데이터 수집 및 기술적 분석 에이전트
1분마다 OHLCV 데이터를 수집하고 기술적 지표를 계산합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable

import pandas as pd
from loguru import logger

from agents.base_agent import BaseAgent, AgentStatus
from exchange.connector import ExchangeConnector
from core.config import settings


@dataclass
class MarketSignal:
    """시장 분석 결과 신호"""
    symbol: str
    exchange: str
    direction: str          # BULLISH | BEARISH | NEUTRAL
    confidence: float       # 0.0 ~ 1.0
    indicators: dict = field(default_factory=dict)
    price: float = 0.0
    volume_24h: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "direction": self.direction,
            "confidence": self.confidence,
            "indicators": self.indicators,
            "price": self.price,
            "volume_24h": self.volume_24h,
            "timestamp": self.timestamp.isoformat(),
        }


class MarketAnalyzerAgent(BaseAgent):
    """
    시장 분석 에이전트
    
    역할:
    - 거래소에서 OHLCV, 티커 데이터 수집
    - RSI, MACD, 볼린저 밴드 등 기술적 지표 계산
    - 시장 방향성 (BULLISH/BEARISH/NEUTRAL) 판단
    - MarketSignal을 StrategyAgent에 전달
    """

    agent_type = "market_analyzer"

    def __init__(
        self,
        exchange: ExchangeConnector,
        symbols: Optional[List[str]] = None,
        on_signal: Optional[Callable[[MarketSignal], None]] = None,
    ):
        super().__init__()
        self.exchange = exchange
        self.symbols = symbols or settings.DEFAULT_SYMBOLS
        self.on_signal = on_signal  # 신호 수신 콜백 (StrategyAgent로 전달)
        self.latest_signals: Dict[str, MarketSignal] = {}

    async def run_cycle(self):
        """시장 데이터 수집 및 분석 사이클"""
        await self._log("INFO", f"시장 분석 시작: {self.symbols}")

        for symbol in self.symbols:
            try:
                signal = await self._analyze_symbol(symbol)
                self.latest_signals[symbol] = signal

                await self._log(
                    "DECISION",
                    f"{symbol} 분석 완료: {signal.direction} (신뢰도={signal.confidence:.2%})",
                    signal.to_dict(),
                )

                # 콜백으로 StrategyAgent에 신호 전달
                if self.on_signal:
                    await self.on_signal(signal)

            except Exception as e:
                await self._log("ERROR", f"{symbol} 분석 실패: {e}")

    async def _analyze_symbol(self, symbol: str) -> MarketSignal:
        """단일 심볼 분석"""
        # 1. 현재 가격 조회
        ticker = await self.exchange.fetch_ticker(symbol)
        current_price = ticker["last"]
        volume_24h = ticker.get("quoteVolume", 0)

        # 2. OHLCV 데이터 수집 (1시간봉 200개)
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe="1h", limit=200)

        if not ohlcv:
            return MarketSignal(
                symbol=symbol,
                exchange=self.exchange.exchange_id,
                direction="NEUTRAL",
                confidence=0.0,
                price=current_price,
            )

        # 3. DataFrame 변환
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")

        # 4. 기술적 지표 계산
        indicators = self._calculate_indicators(df)

        # 5. 시장 방향성 판단
        direction, confidence = self._determine_direction(indicators)

        return MarketSignal(
            symbol=symbol,
            exchange=self.exchange.exchange_id,
            direction=direction,
            confidence=confidence,
            indicators=indicators,
            price=current_price,
            volume_24h=volume_24h,
        )

    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """기술적 지표 계산"""
        import ta

        indicators = {}

        try:
            # RSI
            rsi = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi()
            indicators["rsi"] = round(float(rsi.iloc[-1]), 2)

            # MACD
            macd = ta.trend.MACD(close=df["close"])
            indicators["macd"] = round(float(macd.macd().iloc[-1]), 6)
            indicators["macd_signal"] = round(float(macd.macd_signal().iloc[-1]), 6)
            indicators["macd_diff"] = round(float(macd.macd_diff().iloc[-1]), 6)

            # 볼린저 밴드
            bb = ta.volatility.BollingerBands(close=df["close"])
            indicators["bb_upper"] = round(float(bb.bollinger_hband().iloc[-1]), 2)
            indicators["bb_lower"] = round(float(bb.bollinger_lband().iloc[-1]), 2)
            indicators["bb_middle"] = round(float(bb.bollinger_mavg().iloc[-1]), 2)

            # 이동평균선
            indicators["ma20"] = round(float(df["close"].rolling(20).mean().iloc[-1]), 2)
            indicators["ma50"] = round(float(df["close"].rolling(50).mean().iloc[-1]), 2)
            indicators["ma200"] = round(float(df["close"].rolling(200).mean().iloc[-1]), 2)

            # 현재가
            indicators["price"] = round(float(df["close"].iloc[-1]), 2)

            # 거래량 변화율 (24시간 대비)
            avg_volume = float(df["volume"].rolling(24).mean().iloc[-1])
            latest_volume = float(df["volume"].iloc[-1])
            indicators["volume_ratio"] = round(latest_volume / (avg_volume + 1e-10), 2)

        except Exception as e:
            logger.warning(f"지표 계산 부분 실패: {e}")

        return indicators

    def _determine_direction(self, indicators: dict) -> tuple[str, float]:
        """지표 종합하여 시장 방향성 판단"""
        bullish_score = 0
        bearish_score = 0
        total_checks = 0

        # RSI 판단
        if "rsi" in indicators:
            rsi = indicators["rsi"]
            total_checks += 1
            if rsi < 40:
                bullish_score += 1
            elif rsi > 60:
                bearish_score += 1

        # MACD 판단
        if "macd_diff" in indicators:
            diff = indicators["macd_diff"]
            total_checks += 1
            if diff > 0:
                bullish_score += 1
            elif diff < 0:
                bearish_score += 1

        # 이동평균선 판단 (가격 vs MA50)
        if "price" in indicators and "ma50" in indicators:
            total_checks += 1
            if indicators["price"] > indicators["ma50"]:
                bullish_score += 1
            else:
                bearish_score += 1

        # 볼린저 밴드 판단
        if "bb_lower" in indicators and "bb_upper" in indicators and "price" in indicators:
            total_checks += 1
            price = indicators["price"]
            if price < indicators["bb_lower"]:
                bullish_score += 1
            elif price > indicators["bb_upper"]:
                bearish_score += 1

        if total_checks == 0:
            return "NEUTRAL", 0.0

        bull_ratio = bullish_score / total_checks
        bear_ratio = bearish_score / total_checks

        if bull_ratio > 0.6:
            return "BULLISH", bull_ratio
        elif bear_ratio > 0.6:
            return "BEARISH", bear_ratio
        else:
            return "NEUTRAL", 0.5
