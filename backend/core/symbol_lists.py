"""
바이낸스 USDT 현물 심볼 목록 (유동성·섹터 다양화)

- WATCHLIST_SYMBOLS: 시황 워치리스트·차트 선택·Pick 스캐너 기본 후보
- DEFAULT_AGENT_SYMBOLS: MarketAnalyzer 등 주기 분석 대상 (API 부담 고려해 워치리스트보다 짧게 유지 가능)
"""
from typing import List

# 워치리스트 / UI 드롭다운 (약 32종 — L1·L2·DeFi·결제·메타 등)
WATCHLIST_SYMBOLS: List[str] = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "AVAX/USDT",
    "DOT/USDT",
    "LINK/USDT",
    "LTC/USDT",
    "TRX/USDT",
    "ATOM/USDT",
    "NEAR/USDT",
    "ARB/USDT",
    "OP/USDT",
    "UNI/USDT",
    "APT/USDT",
    "SUI/USDT",
    "INJ/USDT",
    "FIL/USDT",
    "TIA/USDT",
    "WLD/USDT",
    "SHIB/USDT",
    "ETC/USDT",
    "AAVE/USDT",
    "HBAR/USDT",
    "ICP/USDT",
    "STX/USDT",
    "TON/USDT",
    "BCH/USDT",
    "RENDER/USDT",
]

# 에이전트가 N초마다 OHLCV+티커 조회 — 과다 시 거래소 rate limit 위험
DEFAULT_AGENT_SYMBOLS: List[str] = WATCHLIST_SYMBOLS[:22]
