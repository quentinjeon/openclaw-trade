"""
Larry Williams 스타일 — Williams %R 기반 매매

래리 윌리엄스가 널리 쓰는 방식:
  - %R은 -100 ~ 0. 과매도 -80 이하, 과매수 -20 이상(0에 가까움).
  - 매수: %R이 -80 선을 **아래에서 위로 돌파**(과매도 탈출, 모멘텀 전환).
  - 매도: %R이 -20 선을 **위에서 아래로 이탈**(과매수 이탈) 또는 극단 과매수 후 하락.

거래량 필터: 평균 대비 1.1배 이상일 때 매수 신뢰도 가산 (가짜 돌파 완화).
"""
import pandas as pd
import numpy as np
from loguru import logger

from strategies.base_strategy import BaseStrategy, StrategySignal


def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series, lbp: int) -> pd.Series:
    """Williams %R (-100 ~ 0). Larry Williams 표준."""
    hh = high.rolling(lbp).max()
    ll = low.rolling(lbp).min()
    den = (hh - ll).replace(0, np.nan)
    return ((hh - close) / den * -100).fillna(-50.0)


class LarryWilliamsStrategy(BaseStrategy):
    """Larry Williams %R 돌파형 역추세/모멘텀 전략"""

    strategy_name = "larry_williams"
    description = "Larry Williams %R (-80/-20 돌파 + 거래량 확인)"

    def default_params(self) -> dict:
        return {
            "lbp": 14,
            "oversold_line": -80.0,
            "overbought_line": -20.0,
            "volume_ma": 20,
            "min_volume_ratio": 1.1,
        }

    def generate_signal(self, df: pd.DataFrame) -> StrategySignal:
        lbp = int(self.params["lbp"])
        os_line = float(self.params["oversold_line"])
        ob_line = float(self.params["overbought_line"])
        vol_n = int(self.params["volume_ma"])
        min_vr = float(self.params["min_volume_ratio"])

        if not self._validate_df(df, min_rows=max(lbp + 5, vol_n + 5)):
            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.0,
                reasoning="데이터 부족",
            )

        try:
            d = df.copy()
            wr = _williams_r(d["high"], d["low"], d["close"], lbp)
            d["_wr"] = wr
            w0 = float(wr.iloc[-1])
            w1 = float(wr.iloc[-2])
            vol_ratio = float(d["volume"].iloc[-1] / (d["volume"].rolling(vol_n).mean().iloc[-1] + 1e-10))

            # ── 매수: %R이 과매도역에서 -80 위로 돌파 (전봉 이하, 금봉 초과)
            if w1 <= os_line and w0 > os_line:
                base = 0.62 + min(0.28, (os_line - w1) / 100.0)
                if vol_ratio >= min_vr:
                    base = min(0.92, base + 0.12)
                else:
                    base = max(0.58, base - 0.08)
                return StrategySignal(
                    action="BUY",
                    strategy_name=self.strategy_name,
                    confidence=min(0.95, base),
                    reasoning=(
                        f"Williams %R 과매도탈출: {w1:.1f}→{w0:.1f} (기준 {os_line}), "
                        f"거래량비 {vol_ratio:.2f}x"
                    ),
                    indicators={"williams_r": round(w0, 2), "volume_ratio": round(vol_ratio, 2)},
                )

            # ── 매도: %R이 과매수역 -20 아래로 이탈
            if w1 >= ob_line and w0 < ob_line:
                conf = 0.58 + min(0.25, (w1 - ob_line) / 80.0)
                return StrategySignal(
                    action="SELL",
                    strategy_name=self.strategy_name,
                    confidence=min(0.9, conf),
                    reasoning=(
                        f"Williams %R 과매수이탈: {w1:.1f}→{w0:.1f} (기준 {ob_line})"
                    ),
                    indicators={"williams_r": round(w0, 2)},
                )

            # 극과매수에서 급락 시작 (보조 매도)
            if w0 >= -5 and w1 > w0 + 15:
                return StrategySignal(
                    action="SELL",
                    strategy_name=self.strategy_name,
                    confidence=0.55,
                    reasoning=f"Williams %R 극단권 하락 전환 {w1:.1f}→{w0:.1f}",
                    indicators={"williams_r": round(w0, 2)},
                )

            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.5,
                reasoning=f"Williams %R={w0:.1f} (중립 구간)",
                indicators={"williams_r": round(w0, 2), "volume_ratio": round(vol_ratio, 2)},
            )

        except Exception as e:
            logger.error(f"LarryWilliams 신호 오류: {e}")
            return StrategySignal(
                action="HOLD",
                strategy_name=self.strategy_name,
                confidence=0.0,
                reasoning=str(e),
            )
