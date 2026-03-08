"""
RSI (Relative Strength Index) 역추세 전략
RSI 과매도 구간에서 매수, 과매수 구간에서 매도
"""
import pandas as pd
import ta
from loguru import logger

from strategies.base_strategy import BaseStrategy, StrategySignal


class RSIStrategy(BaseStrategy):
    """
    RSI 역추세 전략
    - RSI < oversold (기본 30) → BUY
    - RSI > overbought (기본 70) → SELL
    - 그 외 → HOLD
    """

    strategy_name = "rsi_reversal"
    description = "RSI 역추세 전략 (과매도 매수, 과매수 매도)"

    def default_params(self) -> dict:
        return {
            "period": 14,
            "oversold": 30.0,
            "overbought": 70.0,
        }

    def generate_signal(self, df: pd.DataFrame) -> StrategySignal:
        """RSI 기반 매매 신호 생성"""
        if not self._validate_df(df, min_rows=self.params["period"] + 10):
            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.0,
                reasoning="데이터 부족으로 HOLD",
            )

        try:
            # RSI 계산
            rsi_indicator = ta.momentum.RSIIndicator(
                close=df["close"],
                window=self.params["period"],
            )
            df = df.copy()
            df["rsi"] = rsi_indicator.rsi()

            latest_rsi = df["rsi"].iloc[-1]
            prev_rsi = df["rsi"].iloc[-2]

            oversold = self.params["oversold"]
            overbought = self.params["overbought"]

            # 신호 판단
            if latest_rsi < oversold and prev_rsi >= oversold:
                # RSI가 과매도 구간에 진입
                confidence = min((oversold - latest_rsi) / oversold, 1.0)
                return StrategySignal(
                    action="BUY",
                    strategy_name=self.strategy_name,
                    confidence=confidence,
                    reasoning=f"RSI={latest_rsi:.1f} 과매도 구간 진입 (기준: {oversold})",
                    indicators={"rsi": round(latest_rsi, 2)},
                )

            elif latest_rsi > overbought and prev_rsi <= overbought:
                # RSI가 과매수 구간에 진입
                confidence = min((latest_rsi - overbought) / (100 - overbought), 1.0)
                return StrategySignal(
                    action="SELL",
                    strategy_name=self.strategy_name,
                    confidence=confidence,
                    reasoning=f"RSI={latest_rsi:.1f} 과매수 구간 진입 (기준: {overbought})",
                    indicators={"rsi": round(latest_rsi, 2)},
                )

            else:
                return StrategySignal(
                    action="HOLD",
                    strategy_name=self.strategy_name,
                    confidence=0.5,
                    reasoning=f"RSI={latest_rsi:.1f} 중립 구간",
                    indicators={"rsi": round(latest_rsi, 2)},
                )

        except Exception as e:
            logger.error(f"RSI 신호 생성 오류: {e}")
            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.0,
                reasoning=f"오류 발생: {e}",
            )
