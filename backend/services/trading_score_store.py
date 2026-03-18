"""대시보드용 최신 매수·매도·보유 점수 스냅샷 (스레드 안전 단순 저장)."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class TradingScoreStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_symbol: Dict[str, Dict[str, Any]] = {}
        self._updated_at: Optional[datetime] = None

    def update(self, symbol: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._by_symbol[symbol] = payload
            self._updated_at = datetime.utcnow()

    def update_many(self, items: Dict[str, Dict[str, Any]]) -> None:
        with self._lock:
            self._by_symbol.update(items)
            self._updated_at = datetime.utcnow()

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._by_symbol.values())

    def get_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._by_symbol.get(symbol)

    def snapshot_meta(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "symbol_count": len(self._by_symbol),
                "updated_at": self._updated_at.isoformat() + "Z"
                if self._updated_at
                else None,
            }


trading_score_store = TradingScoreStore()
