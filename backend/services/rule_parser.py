"""
Text-to-Rule 파서 (자연어 → 조건식 JSON)

Layer 1: 패턴 매칭 (정규식 기반, 항상 동작)
Layer 2: LLM 파싱 (OPENAI_API_KEY 설정 시)

지원 패턴 (한국어 + 영어):
  - RSI 관련: "RSI가 30 이하", "RSI < 30", "RSI 30 아래", "RSI 70 이상"
  - MACD 관련: "MACD 골든크로스", "MACD 데드크로스", "MACD 히스토그램 양수"
  - 이동평균: "20일선 위", "MA20 돌파", "골든크로스", "데드크로스"
  - 볼린저밴드: "볼린저 하단 이탈", "볼린저 상단 돌파", "볼린저 중심선 위"
  - 거래량: "거래량 평균의 1.5배", "거래량 급증"
  - 가격: "현재가 MA20 위", "종가 > MA50"
"""
import re
import uuid
from typing import Optional, List
from loguru import logger


# ──────────────────────────────────────────────
# 조건 생성 헬퍼
# ──────────────────────────────────────────────

def _make_cond(
    indicator_a: str,
    operator: str,
    *,
    value_b: Optional[float] = None,
    indicator_b: Optional[str] = None,
    params_a: Optional[dict] = None,
    params_b: Optional[dict] = None,
) -> dict:
    """단일 조건 dict 생성"""
    cond = {
        "id": f"cond_{uuid.uuid4().hex[:8]}",
        "indicator_a": indicator_a,
        "params_a": params_a or {},
        "operator": operator,
    }
    if indicator_b is not None:
        cond["type_b"] = "indicator"
        cond["indicator_b"] = indicator_b
        cond["params_b"] = params_b or {}
    else:
        cond["type_b"] = "value"
        cond["value_b"] = value_b if value_b is not None else 0
    return cond


def _make_group(logic: str, conditions: list) -> dict:
    return {"logic": logic, "conditions": conditions}


# ──────────────────────────────────────────────
# 내장 패턴 라이브러리
# ──────────────────────────────────────────────

def _extract_number(text: str, default: float = 14) -> float:
    """텍스트에서 첫 번째 숫자 추출"""
    m = re.search(r'(\d+\.?\d*)', text)
    return float(m.group(1)) if m else default


def _extract_two_numbers(text: str, defaults=(14, 30)) -> tuple:
    """텍스트에서 두 번째 숫자까지 추출"""
    nums = re.findall(r'\d+\.?\d*', text)
    a = float(nums[0]) if len(nums) > 0 else defaults[0]
    b = float(nums[1]) if len(nums) > 1 else defaults[1]
    return a, b


# 패턴 → 파서 함수 매핑 (순서 중요: 더 구체적인 패턴이 앞에 와야 함)
def _parse_patterns(text: str) -> Optional[List[dict]]:
    """
    자연어 텍스트를 조건 딕셔너리 리스트로 변환.
    매칭 실패 시 None 반환.
    """
    t = text.strip().lower()

    # ── RSI 패턴 ────────────────────────────────
    # "RSI(14) <= 30" — period를 명시적으로 괄호 안에 쓴 경우
    m = re.search(r'rsi\((\d+)\)\s*[가이]?\s*(\d+\.?\d*)\s*(이하|미만|아래|below|<|<=)', t)
    if m:
        period = int(m.group(1))
        value = float(m.group(2))
        op = "<=" if m.group(3) in ("이하", "<=", "below") else "<"
        return [_make_cond("RSI", op, value_b=value, params_a={"period": period})]

    # "RSI 30 이하", "RSI가 30 미만", "RSI < 30" (period 기본 14)
    m = re.search(r'rsi[가이]?\s*(\d+\.?\d*)\s*(이하|미만|아래|below|<=|<(?!=))', t)
    if m:
        value = float(m.group(1))
        op_str = m.group(2)
        op = "<=" if op_str in ("이하", "<=", "below") else "<"
        return [_make_cond("RSI", op, value_b=value, params_a={"period": 14})]

    # "RSI(14) >= 70" — period 명시
    m = re.search(r'rsi\((\d+)\)\s*[가이]?\s*(\d+\.?\d*)\s*(이상|초과|위|above|>|>=)', t)
    if m:
        period = int(m.group(1))
        value = float(m.group(2))
        op = ">=" if m.group(3) in ("이상", ">=", "above") else ">"
        return [_make_cond("RSI", op, value_b=value, params_a={"period": period})]

    # "RSI 70 이상" (period 기본 14)
    m = re.search(r'rsi[가이]?\s*(\d+\.?\d*)\s*(이상|초과|above|>=|>(?!=))', t)
    if m:
        value = float(m.group(1))
        op_str = m.group(2)
        op = ">=" if op_str in ("이상", ">=", "above") else ">"
        return [_make_cond("RSI", op, value_b=value, params_a={"period": 14})]

    # "RSI 과매도", "RSI 30 이하"
    if re.search(r'rsi.*(과매도|oversold)', t):
        return [_make_cond("RSI", "<=", value_b=30, params_a={"period": 14})]

    if re.search(r'rsi.*(과매수|overbought)', t):
        return [_make_cond("RSI", ">=", value_b=70, params_a={"period": 14})]

    # ── MACD 패턴 ───────────────────────────────
    if re.search(r'macd.*(골든|golden|크로스오버|bullish|상향)', t) or re.search(r'macd.*(매수|buy.*signal)', t):
        return [_make_cond("MACD", "crosses_above",
                           indicator_b="MACD_SIGNAL",
                           params_a={"fast": 12, "slow": 26, "signal": 9},
                           params_b={"fast": 12, "slow": 26, "signal": 9})]

    if re.search(r'macd.*(데드|dead|하향|bearish)', t) or re.search(r'macd.*(매도|sell.*signal)', t):
        return [_make_cond("MACD", "crosses_below",
                           indicator_b="MACD_SIGNAL",
                           params_a={"fast": 12, "slow": 26, "signal": 9},
                           params_b={"fast": 12, "slow": 26, "signal": 9})]

    if re.search(r'macd.*(히스토그램|histogram).*(양수|양|positive|>.*0)', t):
        return [_make_cond("MACD_HIST", ">", value_b=0.0, params_a={"fast": 12, "slow": 26, "signal": 9})]

    if re.search(r'macd.*(히스토그램|histogram).*(음수|음|negative|<.*0)', t):
        return [_make_cond("MACD_HIST", "<", value_b=0.0, params_a={"fast": 12, "slow": 26, "signal": 9})]

    # ── 볼린저밴드 패턴 ─────────────────────────
    if re.search(r'(볼린저|bollinger|bb).*(하단|lower|아래).*(이탈|break|돌파|밑)', t):
        return [_make_cond("CLOSE", "<", indicator_b="BB_LOWER",
                           params_b={"period": 20, "std_dev": 2.0})]

    if re.search(r'(볼린저|bollinger|bb).*(상단|upper|위).*(돌파|break)', t):
        return [_make_cond("CLOSE", ">", indicator_b="BB_UPPER",
                           params_b={"period": 20, "std_dev": 2.0})]

    if re.search(r'(볼린저|bollinger|bb).*(하단|lower).*반등', t):
        return [_make_cond("CLOSE", "crosses_above", indicator_b="BB_LOWER",
                           params_b={"period": 20, "std_dev": 2.0})]

    if re.search(r'(볼린저|bollinger|bb).*(중간|중심|middle|center).*(위|above)', t):
        return [_make_cond("CLOSE", ">", indicator_b="BB_MIDDLE",
                           params_b={"period": 20})]

    if re.search(r'(볼린저|bollinger|bb).*(중간|중심|middle|center).*(아래|below)', t):
        return [_make_cond("CLOSE", "<", indicator_b="BB_MIDDLE",
                           params_b={"period": 20})]

    # ── 이동평균 패턴 ───────────────────────────
    # "골든크로스" (MA20 > MA50)
    if re.search(r'(골든|golden).*(크로스|cross)', t):
        m = re.findall(r'\d+', t)
        fast = int(m[0]) if len(m) > 0 else 20
        slow = int(m[1]) if len(m) > 1 else 50
        return [_make_cond("MA", "crosses_above", indicator_b="MA",
                           params_a={"period": fast}, params_b={"period": slow})]

    # "데드크로스" (MA20 < MA50)
    if re.search(r'(데드|dead).*(크로스|cross)', t):
        m = re.findall(r'\d+', t)
        fast = int(m[0]) if len(m) > 0 else 20
        slow = int(m[1]) if len(m) > 1 else 50
        return [_make_cond("MA", "crosses_below", indicator_b="MA",
                           params_a={"period": fast}, params_b={"period": slow})]

    # "MA20 위", "20일 이평선 위", "종가가 20일선 위"
    m = re.search(r'(\d+)\s*일?\s*(이평|ma|ema|이동평균).*[이가]?\s*(위|상단|above|위에)', t)
    if m:
        period = int(m.group(1))
        ind = "EMA" if "ema" in m.group(2) else "MA"
        return [_make_cond("CLOSE", ">", indicator_b=ind, params_b={"period": period})]

    m = re.search(r'(이평|ma|ema|이동평균)\s*\(?(\d+)\)?.*[이가]?\s*(위|상단|above|위에)', t)
    if m:
        period = int(m.group(2))
        ind = "EMA" if "ema" in m.group(1) else "MA"
        return [_make_cond("CLOSE", ">", indicator_b=ind, params_b={"period": period})]

    m = re.search(r'(\d+)\s*일?\s*(이평|ma|ema|이동평균).*[이가]?\s*(아래|하단|below)', t)
    if m:
        period = int(m.group(1))
        ind = "EMA" if "ema" in m.group(2) else "MA"
        return [_make_cond("CLOSE", "<", indicator_b=ind, params_b={"period": period})]

    # ── 거래량 패턴 ─────────────────────────────
    # "거래량이 20일 평균의 2배 이상" → period=20, ratio=2.0
    m = re.search(r'거래량.{0,10}(\d+)일\s*평균.{0,5}(\d+\.?\d*)배', t)
    if m:
        vol_period = int(m.group(1))
        ratio = float(m.group(2))
        return [_make_cond("VOLUME_RATIO", ">=", value_b=ratio, params_a={"period": vol_period})]

    # "거래량 평균의 1.5배", "거래량의 1.5배" (period 기본 20)
    # non-digit 문자들 사이에서 숫자를 찾음 (탐욕적 매칭 버그 방지)
    m = re.search(r'거래량[^\d]*(\d+\.?\d*)배', t)
    if m:
        ratio = float(m.group(1))
        return [_make_cond("VOLUME_RATIO", ">=", value_b=ratio, params_a={"period": 20})]

    if re.search(r'거래량.*(급증|surge|폭발|spike)', t):
        return [_make_cond("VOLUME_RATIO", ">=", value_b=2.0, params_a={"period": 20})]

    # ── 스토캐스틱 패턴 ─────────────────────────
    if re.search(r'(스토캐스틱|stoch).*(골든|golden)', t):
        return [_make_cond("STOCH_K", "crosses_above", indicator_b="STOCH_D",
                           params_a={"k_period": 14, "d_period": 3},
                           params_b={"k_period": 14, "d_period": 3})]

    if re.search(r'(스토캐스틱|stoch).*(과매도|oversold|20.*이하|이하.*20)', t):
        return [_make_cond("STOCH_K", "<=", value_b=20.0, params_a={"k_period": 14, "d_period": 3})]

    if re.search(r'(스토캐스틱|stoch).*(과매수|overbought|80.*이상|이상.*80)', t):
        return [_make_cond("STOCH_K", ">=", value_b=80.0, params_a={"k_period": 14, "d_period": 3})]

    # ── 가격 변화율 패턴 ─────────────────────────
    m = re.search(r'(\d+)(봉|캔들|bar)?\s*(상승|오름|rise|up)\s*(\d+\.?\d*)%', t)
    if m:
        period = int(m.group(1))
        pct = float(m.group(4))
        return [_make_cond("PRICE_CHANGE", ">=", value_b=pct, params_a={"period": period})]

    return None


# ──────────────────────────────────────────────
# 복합 패턴 (AND/OR로 합치기)
# ──────────────────────────────────────────────

def _split_conjunction(text: str) -> list:
    """'그리고', '이고', 'AND', '+' 등으로 분리"""
    # 분리자 정규식: 한국어 접속 표현 포함
    separators = r'(?:이고|이며|그리고|\band\b|&|\+|,)'
    parts = re.split(separators, text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def parse_text_to_conditions(text: str) -> dict:
    """
    자연어 텍스트를 ConditionGroup dict로 변환.

    Returns:
        {
          "success": bool,
          "group": ConditionGroup | None,
          "explanation": str,
          "method": "pattern" | "failed",
          "raw_conditions": List[dict]
        }
    """
    if not text or not text.strip():
        return {
            "success": False,
            "group": None,
            "explanation": "텍스트를 입력해주세요.",
            "method": "failed",
            "raw_conditions": [],
        }

    # 복합 조건 분리 시도
    parts = _split_conjunction(text)

    all_conditions = []
    parsed_parts = []

    for part in parts:
        conditions = _parse_patterns(part)
        if conditions:
            all_conditions.extend(conditions)
            parsed_parts.append(part)

    if all_conditions:
        group = _make_group("AND", all_conditions)
        explanation = _generate_explanation(all_conditions)
        return {
            "success": True,
            "group": group,
            "explanation": explanation,
            "method": "pattern",
            "raw_conditions": all_conditions,
        }

    # 전체 텍스트 단일 패턴 시도
    conditions = _parse_patterns(text)
    if conditions:
        group = _make_group("AND", conditions)
        explanation = _generate_explanation(conditions)
        return {
            "success": True,
            "group": group,
            "explanation": explanation,
            "method": "pattern",
            "raw_conditions": conditions,
        }

    # 실패
    logger.warning(f"Text-to-Rule 파싱 실패: '{text}'")
    return {
        "success": False,
        "group": None,
        "explanation": (
            f"'{text}'를 조건으로 변환하지 못했습니다. "
            "더 구체적으로 입력해보세요. "
            "예: 'RSI 30 이하', 'MACD 골든크로스', '거래량 평균의 1.5배'"
        ),
        "method": "failed",
        "raw_conditions": [],
    }


def _generate_explanation(conditions: list) -> str:
    """조건 목록을 사람이 읽기 쉬운 텍스트로 변환"""
    descs = []
    for c in conditions:
        ind_a = c.get("indicator_a", "")
        params_a = c.get("params_a", {})
        op = c.get("operator", "")
        type_b = c.get("type_b", "value")

        # 파라미터 표현
        param_str = ""
        if params_a:
            first_val = list(params_a.values())[0]
            param_str = f"({first_val})"

        # 연산자 한국어 변환
        op_kr = {
            "<=": "이하", ">=": "이상", "<": "미만", ">": "초과",
            "==": "같음", "!=": "다름",
            "crosses_above": "골든크로스 →", "crosses_below": "데드크로스 →",
        }.get(op, op)

        if type_b == "value":
            val = c.get("value_b", 0)
            descs.append(f"{ind_a}{param_str} {op_kr} {val}")
        else:
            ind_b = c.get("indicator_b", "")
            params_b = c.get("params_b", {})
            b_param_str = ""
            if params_b:
                first_val = list(params_b.values())[0]
                b_param_str = f"({first_val})"
            descs.append(f"{ind_a}{param_str} {op_kr} {ind_b}{b_param_str}")

    return " AND ".join(descs)


# ──────────────────────────────────────────────
# 전략 템플릿
# ──────────────────────────────────────────────

STRATEGY_TEMPLATES = {
    "rsi_reversal": {
        "name": "RSI 역추세 전략",
        "description": "RSI 과매도 구간 매수, 과매수 구간 매도",
        "buy_group": _make_group("AND", [
            _make_cond("RSI", "<=", value_b=30, params_a={"period": 14}),
            _make_cond("VOLUME_RATIO", ">=", value_b=1.3, params_a={"period": 20}),
        ]),
        "sell_group": _make_group("OR", [
            _make_cond("RSI", ">=", value_b=70, params_a={"period": 14}),
            _make_cond("PRICE_CHANGE", ">=", value_b=5.0, params_a={"period": 1}),
            _make_cond("PRICE_CHANGE", "<=", value_b=-2.0, params_a={"period": 1}),
        ]),
    },
    "macd_cross": {
        "name": "MACD 골든크로스 전략",
        "description": "MACD 골든크로스 매수, 데드크로스 매도",
        "buy_group": _make_group("AND", [
            _make_cond("MACD", "crosses_above", indicator_b="MACD_SIGNAL",
                       params_a={"fast": 12, "slow": 26, "signal": 9},
                       params_b={"fast": 12, "slow": 26, "signal": 9}),
            _make_cond("RSI", "<", value_b=60, params_a={"period": 14}),
        ]),
        "sell_group": _make_group("OR", [
            _make_cond("MACD", "crosses_below", indicator_b="MACD_SIGNAL",
                       params_a={"fast": 12, "slow": 26, "signal": 9},
                       params_b={"fast": 12, "slow": 26, "signal": 9}),
            _make_cond("PRICE_CHANGE", "<=", value_b=-3.0, params_a={"period": 1}),
        ]),
    },
    "bollinger_reversal": {
        "name": "볼린저밴드 평균회귀 전략",
        "description": "볼린저 하단 이탈 매수, 중심선/상단 매도",
        "buy_group": _make_group("AND", [
            _make_cond("CLOSE", "<=", indicator_b="BB_LOWER",
                       params_b={"period": 20, "std_dev": 2.0}),
            _make_cond("RSI", "<", value_b=40, params_a={"period": 14}),
        ]),
        "sell_group": _make_group("OR", [
            _make_cond("CLOSE", ">=", indicator_b="BB_MIDDLE",
                       params_b={"period": 20}),
            _make_cond("CLOSE", ">=", indicator_b="BB_UPPER",
                       params_b={"period": 20, "std_dev": 2.0}),
        ]),
    },
    "ma_cross": {
        "name": "이동평균선 돌파 전략",
        "description": "MA20이 MA50 상향 돌파 매수, 하향 돌파 매도",
        "buy_group": _make_group("AND", [
            _make_cond("MA", "crosses_above", indicator_b="MA",
                       params_a={"period": 20}, params_b={"period": 50}),
            _make_cond("VOLUME_RATIO", ">=", value_b=1.5, params_a={"period": 20}),
        ]),
        "sell_group": _make_group("OR", [
            _make_cond("MA", "crosses_below", indicator_b="MA",
                       params_a={"period": 20}, params_b={"period": 50}),
            _make_cond("PRICE_CHANGE", "<=", value_b=-3.0, params_a={"period": 1}),
        ]),
    },
    "stochastic_reversal": {
        "name": "스토캐스틱 역추세 전략",
        "description": "스토캐스틱 과매도 구간에서 %K가 %D 상향 돌파 시 매수",
        "buy_group": _make_group("AND", [
            _make_cond("STOCH_K", "<=", value_b=20, params_a={"k_period": 14, "d_period": 3}),
            _make_cond("STOCH_K", "crosses_above", indicator_b="STOCH_D",
                       params_a={"k_period": 14, "d_period": 3},
                       params_b={"k_period": 14, "d_period": 3}),
        ]),
        "sell_group": _make_group("OR", [
            _make_cond("STOCH_K", ">=", value_b=80, params_a={"k_period": 14, "d_period": 3}),
            _make_cond("STOCH_K", "crosses_below", indicator_b="STOCH_D",
                       params_a={"k_period": 14, "d_period": 3},
                       params_b={"k_period": 14, "d_period": 3}),
        ]),
    },
    "larry_williams": {
        "name": "Larry Williams %R",
        "description": "Williams %R -80 돌파 매수, -20 이탈 매도 (거래량 1.15배 확인)",
        "buy_group": _make_group("AND", [
            _make_cond("WILLIAMS_R", "crosses_above", value_b=-80.0, params_a={"lbp": 14}),
            _make_cond("VOLUME_RATIO", ">=", value_b=1.15, params_a={"period": 20}),
        ]),
        "sell_group": _make_group("OR", [
            _make_cond("WILLIAMS_R", "crosses_below", value_b=-20.0, params_a={"lbp": 14}),
            _make_cond("WILLIAMS_R", ">=", value_b=-8.0, params_a={"lbp": 14}),
            _make_cond("PRICE_CHANGE", "<=", value_b=-2.5, params_a={"period": 1}),
        ]),
    },
}
