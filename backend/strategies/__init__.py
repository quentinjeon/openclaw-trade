"""매매 전략 패키지"""
from strategies.rsi_strategy import RSIStrategy
from strategies.macd_strategy import MACDStrategy
from strategies.bollinger_strategy import BollingerStrategy
from strategies.williams_strategy import LarryWilliamsStrategy

AVAILABLE_STRATEGIES = {
    "larry_williams": LarryWilliamsStrategy,
    "rsi_reversal": RSIStrategy,
    "macd_crossover": MACDStrategy,
    "bollinger_bands": BollingerStrategy,
}

# 에이전트 기본: Larry Williams %R 단일 (설정 API로 다른 전략 켤 수 있음)
DEFAULT_ACTIVE_STRATEGIES = ["larry_williams"]

__all__ = [
    "RSIStrategy",
    "MACDStrategy",
    "BollingerStrategy",
    "LarryWilliamsStrategy",
    "AVAILABLE_STRATEGIES",
    "DEFAULT_ACTIVE_STRATEGIES",
]
