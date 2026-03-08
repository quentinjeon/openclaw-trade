"""매매 전략 패키지"""
from strategies.rsi_strategy import RSIStrategy
from strategies.macd_strategy import MACDStrategy
from strategies.bollinger_strategy import BollingerStrategy

AVAILABLE_STRATEGIES = {
    "rsi_reversal": RSIStrategy,
    "macd_crossover": MACDStrategy,
    "bollinger_bands": BollingerStrategy,
}

__all__ = ["RSIStrategy", "MACDStrategy", "BollingerStrategy", "AVAILABLE_STRATEGIES"]
