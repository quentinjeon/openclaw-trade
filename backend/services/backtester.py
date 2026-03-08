"""
백테스트 엔진 (Backtester)

조건 평가 결과를 기반으로 가상 트레이딩 시뮬레이션을 수행합니다.

가정:
  - 매수 신호 발생 봉의 다음 봉 시가(open)에 진입
  - 매도 신호 발생 봉의 다음 봉 시가(open)에 청산
  - 동시에 1개 포지션 (롱 온리)
  - 수수료 0.1% 양방향
  - 슬리피지는 별도 미반영 (향후 추가 예정)
"""
from typing import List, Optional, TypedDict
import pandas as pd
import numpy as np
from loguru import logger

from services.condition_evaluator import evaluate_condition_group


# ──────────────────────────────────────────────
# 타입 정의
# ──────────────────────────────────────────────

class TradeSignal(TypedDict):
    time: int                         # Unix timestamp (초)
    type: str                         # "BUY" | "SELL"
    price: float                      # 진입/청산 가격
    return_pct: Optional[float]       # 수익률 (매도 시점만)
    triggered_conditions: List[str]   # 발동된 조건 설명


class BacktestStats(TypedDict):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float              # %
    avg_return_pct: float        # %
    total_return_pct: float      # % (복리)
    max_return_pct: float        # % (단일 트레이드)
    max_loss_pct: float          # % (단일 트레이드, 음수)
    max_drawdown_pct: float      # % (최대낙폭, 음수)
    avg_holding_bars: float      # 평균 보유 봉 수


class BacktestResult(TypedDict):
    signals: List[TradeSignal]
    stats: BacktestStats
    candle_count: int


# ──────────────────────────────────────────────
# 수수료 상수
# ──────────────────────────────────────────────
COMMISSION_RATE = 0.001  # 0.1% (Binance 기준 Taker fee)


# ──────────────────────────────────────────────
# 조건 설명 텍스트 생성
# ──────────────────────────────────────────────

def _format_condition_desc(cond: dict, df: pd.DataFrame, idx: int) -> str:
    """단일 조건의 실제 값을 포함한 설명 문자열 반환"""
    try:
        from services.condition_evaluator import _compute_indicator
        indicator_a = cond.get("indicator_a", "")
        params_a = cond.get("params_a", {})
        operator = cond.get("operator", "")
        type_b = cond.get("type_b", "value")

        series_a = _compute_indicator(df, indicator_a, params_a)
        val_a = series_a.iloc[idx]

        if type_b == "value":
            value_b = cond.get("value_b", 0)
            param_str = f"({list(params_a.values())[0]})" if params_a else ""
            return f"{indicator_a}{param_str}={round(float(val_a), 2)} {operator} {value_b}"
        else:
            indicator_b = cond.get("indicator_b", "")
            params_b = cond.get("params_b", {})
            series_b = _compute_indicator(df, indicator_b, params_b)
            val_b = series_b.iloc[idx]
            return f"{indicator_a}={round(float(val_a), 2)} {operator} {indicator_b}={round(float(val_b), 2)}"
    except Exception:
        return str(cond.get("indicator_a", "조건"))


# ──────────────────────────────────────────────
# 백테스트 메인 함수
# ──────────────────────────────────────────────

def run_backtest(
    df: pd.DataFrame,
    buy_group: dict,
    sell_group: dict,
) -> BacktestResult:
    """
    OHLCV DataFrame에 대해 백테스트를 실행합니다.

    Args:
        df: OHLCV DataFrame (time, open, high, low, close, volume 컬럼 필수)
            time은 Unix timestamp (초)
        buy_group: 매수 ConditionGroup dict
        sell_group: 매도 ConditionGroup dict

    Returns:
        BacktestResult: 신호 목록 + 통계
    """
    if len(df) < 10:
        return BacktestResult(
            signals=[],
            stats=_empty_stats(),
            candle_count=len(df),
        )

    df = df.reset_index(drop=True).copy()

    # 조건 평가 (벡터 연산)
    buy_signals = evaluate_condition_group(df, buy_group)
    sell_signals = evaluate_condition_group(df, sell_group)

    buy_conditions = buy_group.get("conditions", [])
    sell_conditions = sell_group.get("conditions", [])

    signals: List[TradeSignal] = []
    trades: List[dict] = []

    in_position = False
    entry_price = 0.0
    entry_bar = 0

    # ── 시뮬레이션 루프 ──────────────────────────────
    for i in range(len(df) - 1):  # 마지막 봉은 다음 봉 없으므로 제외
        current_time = int(df["time"].iloc[i])
        next_open = float(df["open"].iloc[i + 1])

        if not in_position:
            # 매수 신호: 다음 봉 시가에 진입
            if buy_signals.iloc[i]:
                triggered = [
                    _format_condition_desc(c, df, i)
                    for c in buy_conditions
                    if _is_condition_true(c, df, i)
                ]
                signals.append(TradeSignal(
                    time=current_time,
                    type="BUY",
                    price=next_open,
                    return_pct=None,
                    triggered_conditions=triggered,
                ))
                entry_price = next_open * (1 + COMMISSION_RATE)  # 수수료 포함
                entry_bar = i + 1
                in_position = True

        else:
            # 매도 신호: 다음 봉 시가에 청산
            if sell_signals.iloc[i]:
                exit_price = next_open * (1 - COMMISSION_RATE)  # 수수료 포함
                return_pct = (exit_price - entry_price) / entry_price * 100

                triggered = [
                    _format_condition_desc(c, df, i)
                    for c in sell_conditions
                    if _is_condition_true(c, df, i)
                ]
                signals.append(TradeSignal(
                    time=current_time,
                    type="SELL",
                    price=next_open,
                    return_pct=round(return_pct, 4),
                    triggered_conditions=triggered,
                ))
                trades.append({
                    "return_pct": return_pct,
                    "holding_bars": (i + 1) - entry_bar,
                })
                in_position = False

    # 마지막 포지션 미청산 처리 (강제 청산 없음)
    stats = _calculate_stats(trades, df)

    return BacktestResult(
        signals=signals,
        stats=stats,
        candle_count=len(df),
    )


def _is_condition_true(cond: dict, df: pd.DataFrame, idx: int) -> bool:
    """특정 인덱스에서 단일 조건이 True인지 확인"""
    try:
        from services.condition_evaluator import _evaluate_single_condition
        result = _evaluate_single_condition(df, cond)
        return bool(result.iloc[idx])
    except Exception:
        return False


def _empty_stats() -> BacktestStats:
    return BacktestStats(
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        win_rate=0.0,
        avg_return_pct=0.0,
        total_return_pct=0.0,
        max_return_pct=0.0,
        max_loss_pct=0.0,
        max_drawdown_pct=0.0,
        avg_holding_bars=0.0,
    )


def _calculate_stats(trades: list, df: pd.DataFrame) -> BacktestStats:
    """거래 목록에서 통계를 계산합니다"""
    if not trades:
        return _empty_stats()

    returns = [t["return_pct"] for t in trades]
    holding_bars = [t["holding_bars"] for t in trades]

    winning = [r for r in returns if r > 0]
    losing = [r for r in returns if r <= 0]

    # 복리 총 수익률
    total_return = 1.0
    for r in returns:
        total_return *= (1 + r / 100)
    total_return_pct = (total_return - 1) * 100

    # 최대 낙폭 (MDD) 계산
    cumulative = [1.0]
    for r in returns:
        cumulative.append(cumulative[-1] * (1 + r / 100))

    peak = cumulative[0]
    max_dd = 0.0
    for val in cumulative:
        if val > peak:
            peak = val
        dd = (val - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    return BacktestStats(
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate=round(len(winning) / len(trades) * 100, 1) if trades else 0.0,
        avg_return_pct=round(float(np.mean(returns)), 2),
        total_return_pct=round(total_return_pct, 2),
        max_return_pct=round(max(returns), 2),
        max_loss_pct=round(min(returns), 2),
        max_drawdown_pct=round(max_dd, 2),
        avg_holding_bars=round(float(np.mean(holding_bars)), 1),
    )
