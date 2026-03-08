"""
시스템 설정 모듈
pydantic-settings를 사용하여 환경변수에서 설정을 로드합니다.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """OpenClaw 시스템 설정"""

    # 앱 기본 설정
    APP_NAME: str = "OpenClaw Trading System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | production

    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # 데이터베이스
    DATABASE_URL: str = "sqlite+aiosqlite:///./openclaw.db"

    # Redis (선택사항)
    REDIS_URL: Optional[str] = None

    # 거래소 API 키 (페이퍼트레이딩은 불필요)
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_SECRET_KEY: Optional[str] = None
    BINANCE_TESTNET: bool = True  # 기본값: 테스트넷

    UPBIT_API_KEY: Optional[str] = None
    UPBIT_SECRET_KEY: Optional[str] = None

    BYBIT_API_KEY: Optional[str] = None
    BYBIT_SECRET_KEY: Optional[str] = None

    # 기본 거래 설정
    DEFAULT_EXCHANGE: str = "binance"
    DEFAULT_SYMBOLS: List[str] = ["BTC/USDT", "ETH/USDT"]
    PAPER_TRADING: bool = True  # 기본값: 페이퍼트레이딩 (안전)
    PAPER_TRADING_BALANCE: float = 10000.0  # 가상 잔고 (USDT)

    # 에이전트 설정
    MARKET_ANALYZER_INTERVAL: int = 60  # 초
    PORTFOLIO_UPDATE_INTERVAL: int = 60  # 초

    # 리스크 기본 설정
    MAX_POSITION_SIZE_PCT: float = 5.0   # 계좌의 최대 5%
    MAX_OPEN_POSITIONS: int = 5
    DAILY_LOSS_LIMIT_PCT: float = 3.0   # 일일 최대 손실 3%
    DEFAULT_STOP_LOSS_PCT: float = 2.0  # 기본 손절 2%
    DEFAULT_TAKE_PROFIT_PCT: float = 4.0  # 기본 익절 4%

    # 전략 기본 설정
    RSI_PERIOD: int = 14
    RSI_OVERSOLD: float = 30.0
    RSI_OVERBOUGHT: float = 70.0
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            # JSON 배열 형식 처리: ["a","b"]
            if v.startswith("["):
                import json
                return json.loads(v)
            # 쉼표 구분 문자열 처리: a,b
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("DEFAULT_SYMBOLS", mode="before")
    @classmethod
    def parse_symbols(cls, v):
        if isinstance(v, str):
            v = v.strip()
            # JSON 배열 형식 처리: ["a","b"]
            if v.startswith("["):
                import json
                return json.loads(v)
            # 쉼표 구분 문자열 처리: a,b
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # NEXT_PUBLIC_* 등 불필요한 환경변수 무시


# 전역 설정 인스턴스
settings = Settings()
