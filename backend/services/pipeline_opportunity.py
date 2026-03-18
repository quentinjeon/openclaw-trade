"""
백테스트 기반 단기 진입 기회 스캔

- 동일 매수 조건(예: Larry Williams %R)이 과거에 발생한 봉에서
  진입(다음 봉 시가) 후 horizon 봉 안 최고가 기준으로
  target_return_pct 이상 도달한 비율 = '확률' 추정.
- 현재 봉에서 매수 조건이 참일 때만 기회로 노출 (버튼 유효).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from core.symbol_lists import WATCHLIST_SYMBOLS
from services.condition_evaluator import evaluate_condition_group
from services.rule_parser import STRATEGY_TEMPLATES


# 5분봉 기준 horizon 봉 수 → 분
def _horizon_to_minutes(timeframe: str, horizon_bars: int) -> int:
    m = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(timeframe, 5)
    return horizon_bars * m


@dataclass
class PipelineOpportunity:
    pipeline_id: str
    symbol: str
    timeframe: str
    window_minutes: int
    horizon_bars: int
    target_return_pct: float
    hit_probability_pct: float
    sample_size: int
    avg_max_gain_pct: float
    live_valid: bool
    valid_until_iso: str
    strategy_key: str
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "window_minutes": self.window_minutes,
            "horizon_bars": self.horizon_bars,
            "target_return_pct": round(self.target_return_pct, 2),
            "hit_probability_pct": round(self.hit_probability_pct, 1),
            "sample_size": self.sample_size,
            "avg_max_gain_pct": round(self.avg_max_gain_pct, 2),
            "live_valid": self.live_valid,
            "valid_until": self.valid_until_iso,
            "strategy_key": self.strategy_key,
            "summary": self.summary,
        }


def _forward_hit_stats(
    df: pd.DataFrame,
    buy_mask: pd.Series,
    horizon_bars: int,
    target_pct: float,
) -> Tuple[float, int, float]:
    """
    buy_mask[i]=True → i봉 종가 후 신호, 진입가 = i+1봉 시가.
    horizon 봉 동안(진입 봉 포함) 고가 대비 최대 수익률 %.
    """
    n = len(df)
    gains: List[float] = []
    hits = 0
    for i in range(n - horizon_bars - 2):
        if i + 1 >= n or not bool(buy_mask.iloc[i]):
            continue
        entry = float(df["open"].iloc[i + 1])
        if entry <= 0:
            continue
        end = min(i + 1 + horizon_bars, n)
        chunk = df["high"].iloc[i + 1 : end]
        if chunk.empty:
            continue
        mx = float(chunk.max())
        g = (mx - entry) / entry * 100.0
        gains.append(g)
        if g >= target_pct:
            hits += 1
    if not gains:
        return 0.0, 0, 0.0
    return hits / len(gains) * 100.0, len(gains), sum(gains) / len(gains)


async def scan_pipeline_opportunities(
    exchange,
    *,
    strategy_key: str = "larry_williams",
    timeframe: str = "5m",
    candle_limit: int = 600,
    horizon_bars: int = 3,
    target_return_pct: float = 2.5,
    min_probability: float = 48.0,
    min_samples: int = 8,
    max_symbols: int = 6,
) -> List[Dict[str, Any]]:
    """
    거래소에서 캔들을 받아 기회 목록 생성.
    live_valid=False 인 항목은 반환하지 않음 (버튼 미노출).
    """
    tmpl = STRATEGY_TEMPLATES.get(strategy_key) or STRATEGY_TEMPLATES["larry_williams"]
    buy_g = tmpl["buy_group"]
    sell_g = tmpl["sell_group"]

    window_minutes = _horizon_to_minutes(timeframe, horizon_bars)
    symbols = WATCHLIST_SYMBOLS[:max_symbols]
    out: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for symbol in symbols:
        try:
            raw = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=min(candle_limit, 1000))
            if not raw or len(raw) < horizon_bars + 50:
                continue
            df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
        except Exception as e:
            logger.debug(f"pipeline scan {symbol}: {e}")
            continue

        try:
            buy_mask = evaluate_condition_group(df, buy_g)
            prob, n_samp, avg_g = _forward_hit_stats(df, buy_mask, horizon_bars, target_return_pct)
        except Exception as e:
            logger.warning(f"pipeline eval {symbol}: {e}")
            continue

        live = False
        try:
            if len(buy_mask) > 0:
                live = bool(buy_mask.iloc[-1])
        except Exception:
            pass

        if not live:
            continue
        if n_samp < min_samples or prob < min_probability:
            continue

        valid_until = now + timedelta(minutes=window_minutes)
        pid = f"{symbol.replace('/', '-')}-{strategy_key}-{int(now.timestamp() // 300)}"

        summary = (
            f"최근 유사 신호 {n_samp}건 중 약 {prob:.0f}%가 진입 후 {window_minutes}분 안 "
            f"+{target_return_pct}% 이상(고가 기준) 도달 (평균 최대 +{avg_g:.1f}%)"
        )

        op = PipelineOpportunity(
            pipeline_id=pid,
            symbol=symbol,
            timeframe=timeframe,
            window_minutes=window_minutes,
            horizon_bars=horizon_bars,
            target_return_pct=target_return_pct,
            hit_probability_pct=prob,
            sample_size=n_samp,
            avg_max_gain_pct=avg_g,
            live_valid=True,
            valid_until_iso=valid_until.replace(microsecond=0).isoformat(),
            strategy_key=strategy_key,
            summary=summary,
        )
        out.append(op.to_dict())

    out.sort(key=lambda x: x["hit_probability_pct"], reverse=True)
    return out


def verify_opportunity_still_live(
    df: pd.DataFrame,
    strategy_key: str,
) -> bool:
    tmpl = STRATEGY_TEMPLATES.get(strategy_key) or STRATEGY_TEMPLATES["larry_williams"]
    buy_g = tmpl["buy_group"]
    try:
        m = evaluate_condition_group(df, buy_g)
        return len(m) > 0 and bool(m.iloc[-1])
    except Exception:
        return False
