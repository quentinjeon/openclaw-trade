"""
OpenAI API 누적 사용액 상한 (기본 $30 미만 유지)

- 실제 LLM 호출이 생기면 호출 전후로 record_spend() 사용.
- 한도 초과 시 can_spend() == False → LLM 경로 스킵.
"""
import json
import os
import threading
from typing import Any, Dict

from loguru import logger

from core.config import settings

_lock = threading.Lock()
_STATE: Dict[str, Any] = {"loaded": False, "total_usd": 0.0}


def _path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(base, "data")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "openai_spend.json")


def _load() -> float:
    p = _path()
    try:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            return float(d.get("total_usd", 0.0))
    except Exception as e:
        logger.warning(f"openai_spend 로드 실패: {e}")
    return 0.0


def _save(total: float) -> None:
    p = _path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"total_usd": round(total, 6), "cap_usd": settings.OPENAI_MAX_SPEND_USD}, f, indent=2)


def get_total_spent_usd() -> float:
    with _lock:
        if not _STATE["loaded"]:
            _STATE["total_usd"] = _load()
            _STATE["loaded"] = True
        return _STATE["total_usd"]


def can_spend(estimated_usd: float) -> bool:
    """이번 호출 예상 비용(USD)을 써도 한도 이내인지."""
    if not settings.OPENAI_API_KEY or not settings.OPENAI_LLM_ENABLED:
        return False
    cap = float(settings.OPENAI_MAX_SPEND_USD)
    if cap <= 0:
        return False
    return get_total_spent_usd() + max(0.0, estimated_usd) < cap


def record_spend(usd: float, note: str = "") -> None:
    """실제 청구액 또는 추정치를 누적 (한도 초과 방지용)."""
    if usd <= 0:
        return
    with _lock:
        if not _STATE["loaded"]:
            _STATE["total_usd"] = _load()
            _STATE["loaded"] = True
        _STATE["total_usd"] += usd
        new_total = _STATE["total_usd"]
        _save(new_total)
    logger.info(f"OpenAI 누적 사용 +${usd:.4f} USD (합계 ${new_total:.4f}) {note}")
