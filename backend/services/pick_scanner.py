"""
백테스트 기반 종목 스코어링 (Pick Scanner)

동일한 매수/매도 조건 템플릿(또는 저장된 조건식)으로 과거 구간 백테스트를 돌리고,
승률·누적수익·MDD·거래횟수를 종합해 0~100 점수를 부여합니다.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from services.backtester import run_backtest
from services.condition_evaluator import evaluate_condition_group
from services.rule_parser import STRATEGY_TEMPLATES


def compute_pick_score(stats: Dict[str, Any]) -> Tuple[float, str]:
    """
    백테스트 통계로 매수 매력도 점수(0~100) 산출.

    구성:
    - 승률 가중 (~40)
    - 누적 수익률 (~25, -20%~+40% 구간 정규화)
    - MDD 완화 (~25, 0%에 가까울수록 높음)
    - 표본 거래 수 (~10, 15회 이상 만점)
    - 거래 3회 미만이면 신뢰도 0.75 배율
    """
    t = int(stats.get("total_trades") or 0)
    if t == 0:
        return 0.0, "과거 구간에 완결된 매매 신호 없음"

    wr = float(stats.get("win_rate") or 0)
    tr = float(stats.get("total_return_pct") or 0)
    mdd = float(stats.get("max_drawdown_pct") or 0)

    s_wr = min(40.0, wr * 0.4)
    s_ret = max(0.0, min(25.0, (tr + 20.0) / 60.0 * 25.0))
    if mdd <= 0:
        s_mdd = max(0.0, min(25.0, (100.0 + mdd) / 100.0 * 25.0))
    else:
        s_mdd = 12.5
    s_n = min(t / 15.0, 1.0) * 10.0

    raw = s_wr + s_ret + s_mdd + s_n
    if t < 3:
        raw *= 0.75
    score = min(100.0, round(raw, 1))
    detail = f"승률 {wr}% · 누적 {tr:.1f}% · MDD {mdd:.1f}% · 완결 {t}회"
    return score, detail


@dataclass
class SymbolPickResult:
    symbol: str
    score: float
    score_detail: str
    win_rate: float
    total_return_pct: float
    max_drawdown_pct: float
    total_trades: int
    avg_return_pct: float
    live_buy_signal: bool
    template_key: str


def _groups_from_config(
    template_key: str,
    condition_row: Optional[Any],
) -> Tuple[Dict, Dict, str]:
    """buy_group, sell_group, 라벨"""
    if condition_row and condition_row.buy_conditions and condition_row.sell_conditions:
        import json

        buy = json.loads(condition_row.buy_conditions)
        sell = json.loads(condition_row.sell_conditions)
        return buy, sell, f"condition#{condition_row.id}"
    tmpl = STRATEGY_TEMPLATES.get(template_key) or STRATEGY_TEMPLATES["rsi_reversal"]
    return tmpl["buy_group"], tmpl["sell_group"], template_key


def analyze_symbol_df(
    symbol: str,
    df: pd.DataFrame,
    buy_group: dict,
    sell_group: dict,
    template_label: str,
) -> SymbolPickResult:
    """단일 심볼 DataFrame에 대해 백테스트 + 현재 봉 매수 신호 여부."""
    if df is None or len(df) < 30:
        return SymbolPickResult(
            symbol=symbol,
            score=0.0,
            score_detail="캔들 부족 (30개 미만)",
            win_rate=0.0,
            total_return_pct=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
            avg_return_pct=0.0,
            live_buy_signal=False,
            template_key=template_label,
        )

    df = df.reset_index(drop=True).copy()
    try:
        result = run_backtest(df, buy_group, sell_group)
        stats = result["stats"]
        score, detail = compute_pick_score(stats)
    except Exception as e:
        logger.warning(f"{symbol} 백테스트 실패: {e}")
        return SymbolPickResult(
            symbol=symbol,
            score=0.0,
            score_detail=str(e),
            win_rate=0.0,
            total_return_pct=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
            avg_return_pct=0.0,
            live_buy_signal=False,
            template_key=template_label,
        )

    live_buy = False
    try:
        buy_vec = evaluate_condition_group(df, buy_group)
        if len(buy_vec) > 0 and bool(buy_vec.iloc[-1]):
            live_buy = True
    except Exception:
        pass

    return SymbolPickResult(
        symbol=symbol,
        score=score,
        score_detail=detail,
        win_rate=float(stats["win_rate"]),
        total_return_pct=float(stats["total_return_pct"]),
        max_drawdown_pct=float(stats["max_drawdown_pct"]),
        total_trades=int(stats["total_trades"]),
        avg_return_pct=float(stats["avg_return_pct"]),
        live_buy_signal=live_buy,
        template_key=template_label,
    )


def result_to_dict(r: SymbolPickResult) -> dict:
    return {
        "symbol": r.symbol,
        "score": r.score,
        "score_detail": r.score_detail,
        "win_rate": r.win_rate,
        "total_return_pct": r.total_return_pct,
        "max_drawdown_pct": r.max_drawdown_pct,
        "total_trades": r.total_trades,
        "avg_return_pct": r.avg_return_pct,
        "live_buy_signal": r.live_buy_signal,
        "template_key": r.template_key,
    }
