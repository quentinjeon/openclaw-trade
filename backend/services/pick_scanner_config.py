"""
백테스트 기반 종목 스캐너 설정 (JSON 파일 영속화)
"""
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional

from loguru import logger

from core.symbol_lists import WATCHLIST_SYMBOLS

DEFAULT_CONFIG: Dict[str, Any] = {
    "auto_buy_enabled": False,
    "min_score": 60.0,
    "template_key": "larry_williams",
    "condition_id": None,
    "timeframe": "1d",
    "candle_limit": 200,
    "symbols": list(WATCHLIST_SYMBOLS[:20]),
    "scan_interval_minutes": 60,
    "require_live_buy_signal": True,
    "max_auto_buys_per_scan": 2,
}


def _config_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "pick_scanner_config.json")


def load_pick_scanner_config() -> Dict[str, Any]:
    """설정 로드 (파일 없으면 기본값)"""
    path = _config_path()
    cfg = deepcopy(DEFAULT_CONFIG)
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            cfg.update({k: v for k, v in loaded.items() if k in DEFAULT_CONFIG})
    except Exception as e:
        logger.warning(f"pick_scanner 설정 로드 실패, 기본값 사용: {e}")
    return cfg


def save_pick_scanner_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """병합 후 저장"""
    cfg = load_pick_scanner_config()
    for k, v in updates.items():
        if k in DEFAULT_CONFIG:
            cfg[k] = v
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    logger.info(f"pick_scanner 설정 저장: {path}")
    return cfg


def validate_symbols(symbols: List[str]) -> List[str]:
    """최대 40개, 중복 제거"""
    seen = []
    for s in symbols:
        s = str(s).strip().upper().replace(" ", "")
        if "/" not in s:
            continue
        if s not in seen:
            seen.append(s)
    return seen[:40]
