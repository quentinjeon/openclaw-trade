"""
조건 평가 엔진 (Condition Evaluator)

사용자 정의 조건식(ConditionGroup JSON)을 OHLCV DataFrame에 대해 평가합니다.

처리 흐름:
  1. ConditionGroup JSON 파싱
  2. 각 조건의 지표를 pandas/ta로 계산
  3. 연산자 적용 (cross 연산자는 이전 봉 비교)
  4. AND/OR 그룹 연산
  5. 각 봉별 True/False 시리즈 반환

지원 지표:
  가격: CLOSE, OPEN, HIGH, LOW, VOLUME
  이동평균: MA(SMA), EMA, VWMA
  오실레이터: RSI, STOCH_K, STOCH_D, CCI
  추세: MACD, MACD_SIGNAL, MACD_HIST, ADX
  변동성: BB_UPPER, BB_MIDDLE, BB_LOWER, BB_WIDTH, ATR
  파생: VOLUME_RATIO, PRICE_CHANGE, CANDLE_BODY
"""
import json
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning("ta 라이브러리 없음. 지표 계산 불가.")


# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────

SUPPORTED_INDICATORS = {
    # 가격
    "CLOSE", "OPEN", "HIGH", "LOW", "VOLUME",
    # 이동평균
    "MA", "EMA", "VWMA",
    # 오실레이터
    "RSI", "STOCH_K", "STOCH_D", "CCI",
    # 추세
    "MACD", "MACD_SIGNAL", "MACD_HIST", "ADX",
    # 변동성
    "BB_UPPER", "BB_MIDDLE", "BB_LOWER", "BB_WIDTH", "ATR",
    # 파생
    "VOLUME_RATIO", "PRICE_CHANGE", "CANDLE_BODY",
    # 상수 (숫자와 비교 시 우측에 오는 값)
    "VALUE",
}

CROSS_OPERATORS = {"crosses_above", "crosses_below"}
COMPARISON_OPERATORS = {"<", ">", "<=", ">=", "==", "!="}
ALL_OPERATORS = CROSS_OPERATORS | COMPARISON_OPERATORS


# ──────────────────────────────────────────────
# 지표 계산 함수
# ──────────────────────────────────────────────

def _compute_indicator(df: pd.DataFrame, name: str, params: dict) -> pd.Series:
    """
    단일 지표를 계산해서 Series로 반환.
    df는 반드시 open, high, low, close, volume 컬럼을 포함해야 함.
    """
    name = name.upper()

    # ── 가격 지표
    if name == "CLOSE":
        return df["close"]
    if name == "OPEN":
        return df["open"]
    if name == "HIGH":
        return df["high"]
    if name == "LOW":
        return df["low"]
    if name == "VOLUME":
        return df["volume"]

    if not TA_AVAILABLE:
        raise ValueError("ta 라이브러리가 설치되지 않아 지표를 계산할 수 없습니다.")

    # ── 이동평균
    period = int(params.get("period", 14))

    if name == "MA":
        return ta.trend.sma_indicator(df["close"], window=period)

    if name == "EMA":
        return ta.trend.ema_indicator(df["close"], window=period)

    if name == "VWMA":
        # 거래량 가중 이동평균 = (close * volume).rolling(n).sum() / volume.rolling(n).sum()
        return (df["close"] * df["volume"]).rolling(period).sum() / df["volume"].rolling(period).sum()

    # ── 오실레이터
    if name == "RSI":
        return ta.momentum.RSIIndicator(df["close"], window=period).rsi()

    if name == "STOCH_K":
        k = int(params.get("k_period", 14))
        d = int(params.get("d_period", 3))
        stoch = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"], window=k, smooth_window=d)
        return stoch.stoch()

    if name == "STOCH_D":
        k = int(params.get("k_period", 14))
        d = int(params.get("d_period", 3))
        stoch = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"], window=k, smooth_window=d)
        return stoch.stoch_signal()

    if name == "CCI":
        return ta.trend.CCIIndicator(df["high"], df["low"], df["close"], window=period).cci()

    # ── 추세/MACD
    if name in ("MACD", "MACD_SIGNAL", "MACD_HIST"):
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        macd_obj = ta.trend.MACD(df["close"], window_fast=fast, window_slow=slow, window_sign=signal)
        if name == "MACD":
            return macd_obj.macd()
        if name == "MACD_SIGNAL":
            return macd_obj.macd_signal()
        if name == "MACD_HIST":
            return macd_obj.macd_diff()

    if name == "ADX":
        return ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=period).adx()

    # ── 볼린저밴드
    if name in ("BB_UPPER", "BB_MIDDLE", "BB_LOWER", "BB_WIDTH"):
        bb_period = int(params.get("period", 20))
        std_dev = float(params.get("std_dev", 2.0))
        bb = ta.volatility.BollingerBands(df["close"], window=bb_period, window_dev=std_dev)
        if name == "BB_UPPER":
            return bb.bollinger_hband()
        if name == "BB_MIDDLE":
            return bb.bollinger_mavg()
        if name == "BB_LOWER":
            return bb.bollinger_lband()
        if name == "BB_WIDTH":
            return bb.bollinger_wband()

    if name == "ATR":
        return ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=period).average_true_range()

    # ── 파생 지표
    if name == "VOLUME_RATIO":
        vol_period = int(params.get("period", 20))
        ma_vol = df["volume"].rolling(vol_period).mean()
        return df["volume"] / ma_vol

    if name == "PRICE_CHANGE":
        change_period = int(params.get("period", 1))
        return df["close"].pct_change(change_period) * 100  # 퍼센트

    if name == "CANDLE_BODY":
        # 캔들 몸통 크기 (%)
        body = (df["close"] - df["open"]).abs()
        return (body / df["open"] * 100)

    raise ValueError(f"지원하지 않는 지표: {name}")


# ──────────────────────────────────────────────
# 단일 조건 평가
# ──────────────────────────────────────────────

def _evaluate_single_condition(df: pd.DataFrame, cond: dict) -> pd.Series:
    """
    단일 조건을 평가해서 Boolean 시리즈 반환.

    cond 구조:
    {
      "indicator_a": "RSI",
      "params_a": {"period": 14},
      "operator": "<=",
      "type_b": "value",          # "value" | "indicator"
      "value_b": 30,              # type_b == "value"일 때
      "indicator_b": "MA",        # type_b == "indicator"일 때
      "params_b": {"period": 20}  # type_b == "indicator"일 때
    }
    """
    try:
        indicator_a = cond.get("indicator_a", "").upper()
        params_a = cond.get("params_a", {})
        operator = cond.get("operator", "")
        type_b = cond.get("type_b", "value")

        if operator not in ALL_OPERATORS:
            raise ValueError(f"지원하지 않는 연산자: {operator}")

        # A 계산
        series_a = _compute_indicator(df, indicator_a, params_a)

        # B 계산 (상수 또는 다른 지표)
        if type_b == "value":
            value_b = float(cond.get("value_b", 0))
            series_b = pd.Series(value_b, index=df.index)
        else:
            indicator_b = cond.get("indicator_b", "").upper()
            params_b = cond.get("params_b", {})
            series_b = _compute_indicator(df, indicator_b, params_b)

        # 크로스 연산자 처리
        if operator == "crosses_above":
            # 현재 봉: A > B, 이전 봉: A <= B
            prev_a = series_a.shift(1)
            prev_b = series_b.shift(1)
            return (series_a > series_b) & (prev_a <= prev_b)

        if operator == "crosses_below":
            # 현재 봉: A < B, 이전 봉: A >= B
            prev_a = series_a.shift(1)
            prev_b = series_b.shift(1)
            return (series_a < series_b) & (prev_a >= prev_b)

        # 비교 연산자
        if operator == "<":
            return series_a < series_b
        if operator == ">":
            return series_a > series_b
        if operator == "<=":
            return series_a <= series_b
        if operator == ">=":
            return series_a >= series_b
        if operator == "==":
            return series_a == series_b
        if operator == "!=":
            return series_a != series_b

    except Exception as e:
        logger.warning(f"조건 평가 오류 ({cond}): {e}")
        # 오류 발생 시 False 시리즈 반환
        return pd.Series(False, index=df.index)

    return pd.Series(False, index=df.index)


# ──────────────────────────────────────────────
# 그룹 조건 평가 (메인)
# ──────────────────────────────────────────────

def evaluate_condition_group(df: pd.DataFrame, group: dict) -> pd.Series:
    """
    ConditionGroup을 평가해서 각 봉별 Boolean 시리즈 반환.

    group 구조:
    {
      "logic": "AND",   # "AND" | "OR"
      "conditions": [...]
    }
    """
    logic = group.get("logic", "AND").upper()
    conditions: List[dict] = group.get("conditions", [])

    if not conditions:
        return pd.Series(False, index=df.index)

    results = [_evaluate_single_condition(df, cond) for cond in conditions]

    if logic == "AND":
        combined = results[0]
        for r in results[1:]:
            combined = combined & r
    else:  # OR
        combined = results[0]
        for r in results[1:]:
            combined = combined | r

    # NaN은 False 처리
    return combined.fillna(False)


def evaluate_from_json(df: pd.DataFrame, condition_json: str) -> pd.Series:
    """
    JSON 문자열로부터 조건을 평가합니다.
    DB에 저장된 buy_conditions / sell_conditions 문자열을 직접 받습니다.
    """
    try:
        group = json.loads(condition_json)
        return evaluate_condition_group(df, group)
    except json.JSONDecodeError as e:
        logger.error(f"조건 JSON 파싱 오류: {e}")
        return pd.Series(False, index=df.index)


def get_current_indicator_values(df: pd.DataFrame, conditions: List[dict]) -> dict:
    """
    최신 봉의 지표 값들을 딕셔너리로 반환.
    check-now 엔드포인트에서 현재 값 표시에 사용.
    """
    values = {}
    for cond in conditions:
        try:
            indicator_a = cond.get("indicator_a", "")
            params_a = cond.get("params_a", {})
            key = f"{indicator_a}({','.join(str(v) for v in params_a.values())})" if params_a else indicator_a
            series = _compute_indicator(df, indicator_a, params_a)
            val = series.iloc[-1]
            if pd.notna(val):
                values[key] = round(float(val), 6)
        except Exception:
            pass
    return values
