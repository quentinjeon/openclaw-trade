"""
볼린저 밴드 (Bollinger Bands) 전략
가격이 하단 밴드 터치 시 매수, 상단 밴드 터치 시 매도
"""
import pandas as pd
import ta
from loguru import logger

from strategies.base_strategy import BaseStrategy, StrategySignal


class BollingerStrategy(BaseStrategy):
    """
    볼린저 밴드 전략
    - 가격 < 하단 밴드 → BUY (과매도)
    - 가격 > 상단 밴드 → SELL (과매수)
    - 하단/상단 사이 → HOLD
    """

    strategy_name = "bollinger_bands"
    description = "볼린저 밴드 전략 (밴드 돌파 매매)"

    def default_params(self) -> dict:
        return {
            "period": 20,
            "std_dev": 2.0,
        }

    def generate_signal(self, df: pd.DataFrame) -> StrategySignal:
        """볼린저 밴드 기반 매매 신호 생성"""
        if not self._validate_df(df, min_rows=self.params["period"] + 5):
            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.0,
                reasoning="데이터 부족으로 HOLD",
            )

        try:
            df = df.copy()
            bb = ta.volatility.BollingerBands(
                close=df["close"],
                window=self.params["period"],
                window_dev=self.params["std_dev"],
            )
            df["bb_upper"] = bb.bollinger_hband()
            df["bb_middle"] = bb.bollinger_mavg()
            df["bb_lower"] = bb.bollinger_lband()
            df["bb_width"] = bb.bollinger_wband()

            latest = df.iloc[-1]
            current_price = latest["close"]
            upper = latest["bb_upper"]
            lower = latest["bb_lower"]
            middle = latest["bb_middle"]
            width = latest["bb_width"]

            # 밴드 내 상대적 위치 (0: 하단, 0.5: 중간, 1: 상단)
            band_position = (current_price - lower) / (upper - lower + 1e-10)

            if current_price < lower:
                # 하단 밴드 이탈 → 강한 매수 신호
                distance_pct = (lower - current_price) / lower * 100
                confidence = min(distance_pct / 2.0, 1.0)  # 2% 이탈 시 최대 신뢰도
                return StrategySignal(
                    action="BUY",
                    strategy_name=self.strategy_name,
                    confidence=confidence,
                    reasoning=(
                        f"하단 밴드 이탈: 가격={current_price:.2f}, 하단={lower:.2f} "
                        f"(이탈폭={distance_pct:.2f}%)"
                    ),
                    indicators={
                        "price": round(current_price, 2),
                        "bb_upper": round(upper, 2),
                        "bb_lower": round(lower, 2),
                        "bb_width": round(width, 4),
                        "band_position": round(band_position, 3),
                    },
                )

            elif current_price > upper:
                # 상단 밴드 이탈 → 강한 매도 신호
                distance_pct = (current_price - upper) / upper * 100
                confidence = min(distance_pct / 2.0, 1.0)
                return StrategySignal(
                    action="SELL",
                    strategy_name=self.strategy_name,
                    confidence=confidence,
                    reasoning=(
                        f"상단 밴드 이탈: 가격={current_price:.2f}, 상단={upper:.2f} "
                        f"(이탈폭={distance_pct:.2f}%)"
                    ),
                    indicators={
                        "price": round(current_price, 2),
                        "bb_upper": round(upper, 2),
                        "bb_lower": round(lower, 2),
                        "bb_width": round(width, 4),
                        "band_position": round(band_position, 3),
                    },
                )

            else:
                return StrategySignal(
                    action="HOLD",
                    strategy_name=self.strategy_name,
                    confidence=0.5,
                    reasoning=f"밴드 내부: 위치={band_position:.2%}",
                    indicators={
                        "band_position": round(band_position, 3),
                        "bb_width": round(width, 4),
                    },
                )

        except Exception as e:
            logger.error(f"볼린저 밴드 신호 생성 오류: {e}")
            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.0,
                reasoning=f"오류 발생: {e}",
            )
