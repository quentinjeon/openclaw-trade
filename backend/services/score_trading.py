"""
매수·매도·보유 유지 점수 (0~100) 산출.

Larry Williams %R, RSI, MACD, 추세(MA), 시장 방향을 조합해
자금 배분 비중(_score_alloc_mult)과 매매 방향 힌트를 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from agents.market_analyzer import MarketSignal


def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series, lbp: int = 14) -> pd.Series:
    hh = high.rolling(lbp).max()
    ll = low.rolling(lbp).min()
    den = (hh - ll).replace(0, np.nan)
    return ((hh - close) / den * -100).fillna(-50.0)


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(n).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(n).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def _macd_hist(close: pd.Series) -> tuple[float, float, float]:
    """최근 2봉 MACD 히스토그램 (상승 시 매수 가산)."""
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sig = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sig
    if len(hist) < 2 or pd.isna(hist.iloc[-1]):
        return 0.0, 0.0, 0.0
    return float(hist.iloc[-1]), float(hist.iloc[-2]), float(macd.iloc[-1])


@dataclass
class TradingScoreResult:
    """심볼별 점수 및 권장 행동."""

    buy_score: float
    sell_score: float
    hold_score: float
    recommended_action: str  # BUY | SELL | HOLD
    alloc_mult: float  # 0.15 ~ 1.0, 리스크 매니저 매수 비중
    breakdown: Dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self, symbol: str, has_position: bool) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "buy_score": round(self.buy_score, 1),
            "sell_score": round(self.sell_score, 1),
            "hold_score": round(self.hold_score, 1),
            "recommended_action": self.recommended_action,
            "has_position": has_position,
            "suggested_position_pct_of_max": round(self.alloc_mult * 100, 1),
            "alloc_mult": round(self.alloc_mult, 3),
            "breakdown": self.breakdown,
        }


def compute_trading_scores(
    df: pd.DataFrame,
    market_signal: MarketSignal,
    has_position: bool,
    entry_price: Optional[float] = None,
    current_price: Optional[float] = None,
) -> TradingScoreResult:
    """
    OHLCV(1h 권장) + 시장 신호로 세 점수 계산.

    - 매수 점수: 과매도 탈출 근처, RSI 낮음, MACD 개선, 상승 추세, BULLISH 가산
    - 매도 점수: 과매수 이탈 근처, RSI 고점, MACD 약화
    - 보유 점수: 포지션 있을 때만 의미 — 매도 압력 낮음·추세 유지·수익 구간이면 상승
    """
    breakdown: Dict[str, Any] = {}
    min_rows = 50
    if df is None or len(df) < min_rows:
        return TradingScoreResult(
            0.0, 0.0, 50.0, "HOLD", 0.2, {"error": "데이터 부족"},
        )

    d = df.copy()
    high, low, close, vol = d["high"], d["low"], d["close"], d["volume"]
    wr = _williams_r(high, low, close)
    w0, w1 = float(wr.iloc[-1]), float(wr.iloc[-2])
    rsi_v = float(_rsi(close).iloc[-1])
    if pd.isna(rsi_v):
        rsi_v = 50.0
    h0, h1, _ = _macd_hist(close)
    sma20 = float(close.rolling(20).mean().iloc[-1])
    last_px = float(close.iloc[-1])

    # ── 매수 점수 (0~100)
    wr_buy = 25.0
    if w1 <= -80 and w0 > -80:
        wr_buy = 92.0
    elif w0 <= -80:
        wr_buy = 78.0
    elif w0 < -65:
        wr_buy = 65.0
    elif w0 < -50:
        wr_buy = 48.0
    elif w0 < -35:
        wr_buy = 32.0
    else:
        wr_buy = max(15.0, 40.0 - (w0 + 20) * 1.2)

    rsi_buy = max(0.0, min(100.0, (55 - rsi_v) / 55 * 100))
    if rsi_v < 30:
        rsi_buy = min(100.0, rsi_buy + 15)

    macd_buy = 50.0
    if h0 > 0 and h0 > h1:
        macd_buy = 82.0
    elif h0 > 0:
        macd_buy = 62.0
    elif h0 > h1:
        macd_buy = 55.0
    else:
        macd_buy = 28.0

    trend_buy = 55.0 if last_px >= sma20 else 38.0
    mkt = 50.0
    if market_signal.direction == "BULLISH":
        mkt = 72.0
    elif market_signal.direction == "BEARISH":
        mkt = 28.0

    buy_score = (
        0.32 * wr_buy + 0.22 * rsi_buy + 0.18 * macd_buy + 0.14 * trend_buy + 0.14 * mkt
    )
    buy_score = float(max(0.0, min(100.0, buy_score)))

    # ── 매도 점수
    wr_sell = 22.0
    if w1 >= -20 and w0 < -20:
        wr_sell = 90.0
    elif w0 >= -15:
        wr_sell = 85.0
    elif w0 >= -25:
        wr_sell = 68.0
    elif w0 >= -40:
        wr_sell = 42.0
    else:
        wr_sell = max(10.0, 35.0 + (w0 + 50) * 0.8)

    if w0 >= -5 and w1 > w0 + 12:
        wr_sell = max(wr_sell, 75.0)

    rsi_sell = max(0.0, min(100.0, (rsi_v - 45) / 40 * 100))
    macd_sell = 75.0 if h0 < 0 and h0 < h1 else (55.0 if h0 < 0 else 30.0)

    sell_score = 0.45 * wr_sell + 0.35 * rsi_sell + 0.20 * macd_sell
    sell_score = float(max(0.0, min(100.0, sell_score)))

    # ── 보유 유지 점수 (포지션 있을 때 청산 억제력)
    pnl_bias = 50.0
    if has_position and entry_price and current_price and entry_price > 0:
        pnl_pct = (current_price - entry_price) / entry_price * 100
        pnl_bias = 50.0 + min(25.0, max(-15.0, pnl_pct * 2.5))
        breakdown["unrealized_pnl_pct"] = round(pnl_pct, 2)

    trend_hold = 72.0 if last_px >= sma20 else 48.0
    anti_sell = max(0.0, 100.0 - sell_score)
    hold_score = 0.38 * anti_sell + 0.28 * trend_hold + 0.22 * pnl_bias + 0.12 * (
        100.0 - min(buy_score, 80.0)
    )
    if not has_position:
        hold_score = max(hold_score, 35.0)
    hold_score = float(max(0.0, min(100.0, hold_score)))

    breakdown.update(
        {
            "williams_r": round(w0, 2),
            "rsi": round(rsi_v, 2),
            "macd_hist": round(h0, 6),
            "vs_sma20": "above" if last_px >= sma20 else "below",
            "market": market_signal.direction,
        }
    )

    # 권장 행동
    margin = 7.0
    min_edge = 38.0

    if has_position:
        if sell_score >= min_edge and sell_score > hold_score + margin:
            rec = "SELL"
        else:
            rec = "HOLD"
    else:
        if buy_score >= min_edge and buy_score > sell_score + margin:
            rec = "BUY"
        else:
            rec = "HOLD"

    # 매수 시 자금 투입 배율: 점수가 높을수록 max_position 에 가깝게
    alloc_mult = 0.18 + 0.82 * (buy_score / 100.0)
    alloc_mult = max(0.15, min(1.0, alloc_mult))
    if rec != "BUY":
        alloc_mult = min(alloc_mult, 0.35)

    return TradingScoreResult(
        buy_score=buy_score,
        sell_score=sell_score,
        hold_score=hold_score,
        recommended_action=rec,
        alloc_mult=alloc_mult if rec == "BUY" else 0.2,
        breakdown=breakdown,
    )


def portfolio_allocation_hint(rows: list) -> Dict[str, Any]:
    """
    대시보드용 포트폴리오 현금 vs 투자 비중 힌트.
    rows: 각 심볼의 to_public_dict 결과 리스트
    """
    flat = [r for r in rows if not r.get("has_position")]
    held = [r for r in rows if r.get("has_position")]

    if not rows:
        return {
            "target_deploy_pct": 0,
            "suggested_cash_pct": 100,
            "summary": "감시 심볼 없음",
        }

    buy_vals = sorted([r["buy_score"] for r in flat], reverse=True)[:4]
    avg_top_buy = sum(buy_vals) / len(buy_vals) if buy_vals else 0.0

    # 매수 기회가 많을수록 투자 비중 상향 (25~88%)
    deploy = 22.0 + (avg_top_buy / 100.0) * 66.0
    deploy = max(15.0, min(88.0, deploy))

    sell_pressure = sum(r["sell_score"] for r in held) / max(1, len(held))
    if held and sell_pressure > 55:
        deploy = max(10.0, deploy - 15.0)

    return {
        "target_deploy_pct": round(deploy, 1),
        "suggested_cash_pct": round(100 - deploy, 1),
        "avg_opportunity_buy_score": round(avg_top_buy, 1),
        "open_positions_count": len(held),
        "summary": (
            f"기회 점수 상위 평균 {avg_top_buy:.0f}점 → "
            f"권장 투자 비중 약 {deploy:.0f}% / 현금 {100 - deploy:.0f}%"
        ),
    }
