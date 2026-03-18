"""현물 잔고에서 현금(스테이블)으로 집계할 통화 코드"""

STABLE_COINS = frozenset(
    {"USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDP", "USDD"}
)
