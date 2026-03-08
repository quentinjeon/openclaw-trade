"""
전략 기본 추상 클래스
모든 매매 전략은 BaseStrategy를 상속해야 합니다.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import pandas as pd


@dataclass
class StrategySignal:
    """전략 신호 결과"""
    action: str                    # BUY | SELL | HOLD
    strategy_name: str
    confidence: float              # 0.0 ~ 1.0
    reasoning: str                 # 매매 근거 설명
    indicators: dict = field(default_factory=dict)    # {"rsi": 32.1, ...}
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BaseStrategy(ABC):
    """
    매매 전략 기본 클래스
    
    새로운 전략 추가 시:
    1. BaseStrategy를 상속
    2. strategy_name 속성 정의
    3. generate_signal() 메서드 구현
    4. backend/agents.md의 전략 목록 업데이트
    """

    strategy_name: str = "base"
    description: str = "기본 전략"

    def __init__(self, params: Optional[dict] = None):
        self.params = params or self.default_params()
        self.enabled = True

    @abstractmethod
    def default_params(self) -> dict:
        """기본 파라미터 반환"""
        ...

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> StrategySignal:
        """
        OHLCV 데이터프레임을 입력받아 매매 신호 생성
        
        Args:
            df: OHLCV 데이터프레임
                컬럼: [timestamp, open, high, low, close, volume]
        
        Returns:
            StrategySignal
        """
        ...

    def _validate_df(self, df: pd.DataFrame, min_rows: int = 50) -> bool:
        """데이터프레임 유효성 검사"""
        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            return False
        if len(df) < min_rows:
            return False
        return True

    def update_params(self, new_params: dict):
        """파라미터 업데이트"""
        self.params.update(new_params)
