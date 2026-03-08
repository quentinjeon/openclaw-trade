"""
MACD (Moving Average Convergence Divergence) 크로스오버 전략
MACD선이 시그널선을 상향돌파 시 매수, 하향돌파 시 매도
"""
import pandas as pd
import ta
from loguru import logger

from strategies.base_strategy import BaseStrategy, StrategySignal


class MACDStrategy(BaseStrategy):
    """
    MACD 크로스오버 전략
    - MACD > Signal (골든크로스) → BUY
    - MACD < Signal (데드크로스) → SELL
    """

    strategy_name = "macd_crossover"
    description = "MACD 크로스오버 전략 (골든크로스 매수, 데드크로스 매도)"

    def default_params(self) -> dict:
        return {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
        }

    def generate_signal(self, df: pd.DataFrame) -> StrategySignal:
        """MACD 기반 매매 신호 생성"""
        min_rows = self.params["slow_period"] + self.params["signal_period"] + 5
        if not self._validate_df(df, min_rows=min_rows):
            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.0,
                reasoning="데이터 부족으로 HOLD",
            )

        try:
            df = df.copy()
            macd_indicator = ta.trend.MACD(
                close=df["close"],
                window_fast=self.params["fast_period"],
                window_slow=self.params["slow_period"],
                window_sign=self.params["signal_period"],
            )
            df["macd"] = macd_indicator.macd()
            df["macd_signal"] = macd_indicator.macd_signal()
            df["macd_diff"] = macd_indicator.macd_diff()

            latest = df.iloc[-1]
            prev = df.iloc[-2]

            macd_val = latest["macd"]
            signal_val = latest["macd_signal"]
            diff_val = latest["macd_diff"]
            prev_diff = prev["macd_diff"]

            # 골든크로스: MACD가 시그널선 상향 돌파
            if diff_val > 0 and prev_diff <= 0:
                confidence = min(abs(diff_val) / (abs(macd_val) + 1e-10), 1.0)
                return StrategySignal(
                    action="BUY",
                    strategy_name=self.strategy_name,
                    confidence=confidence,
                    reasoning=f"MACD 골든크로스: MACD={macd_val:.4f}, Signal={signal_val:.4f}",
                    indicators={
                        "macd": round(macd_val, 6),
                        "macd_signal": round(signal_val, 6),
                        "macd_diff": round(diff_val, 6),
                    },
                )

            # 데드크로스: MACD가 시그널선 하향 돌파
            elif diff_val < 0 and prev_diff >= 0:
                confidence = min(abs(diff_val) / (abs(macd_val) + 1e-10), 1.0)
                return StrategySignal(
                    action="SELL",
                    strategy_name=self.strategy_name,
                    confidence=confidence,
                    reasoning=f"MACD 데드크로스: MACD={macd_val:.4f}, Signal={signal_val:.4f}",
                    indicators={
                        "macd": round(macd_val, 6),
                        "macd_signal": round(signal_val, 6),
                        "macd_diff": round(diff_val, 6),
                    },
                )

            else:
                return StrategySignal(
                    action="HOLD",
                    strategy_name=self.strategy_name,
                    confidence=0.5,
                    reasoning=f"MACD 크로스 없음: diff={diff_val:.6f}",
                    indicators={"macd_diff": round(diff_val, 6)},
                )

        except Exception as e:
            logger.error(f"MACD 신호 생성 오류: {e}")
            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.0,
                reasoning=f"오류 발생: {e}",
            )
