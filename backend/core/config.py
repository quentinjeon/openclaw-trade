"""
시스템 설정 모듈
pydantic-settings를 사용하여 환경변수에서 설정을 로드합니다.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator

from core.symbol_lists import DEFAULT_AGENT_SYMBOLS


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
    BINANCE_TESTNET: bool = False  # True 시 선물 테스트넷 URL (현물 메인넷 실거래는 False)

    UPBIT_API_KEY: Optional[str] = None
    UPBIT_SECRET_KEY: Optional[str] = None

    BYBIT_API_KEY: Optional[str] = None
    BYBIT_SECRET_KEY: Optional[str] = None

    # OpenAI (Text-to-Rule LLM 확장용 — 패턴 파서만 쓰면 비용 0)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MAX_SPEND_USD: float = 30.0   # 누적 $30 미만 (openai_spend.json)
    OPENAI_LLM_ENABLED: bool = False     # True일 때만 LLM 시도 + 예산 차감

    # 거래 수수료 (바이낸스 현물 테이커 기준 %, 한 방향)
    TAKER_FEE_PCT_PER_SIDE: float = 0.1
    # 왕복 최소 비용 ≈ 2배; 익절은 이 이상 남기도록 권장
    ROUND_TRIP_FEE_PCT_APPROX: float = 0.2

    # 기본 거래 설정
    DEFAULT_EXCHANGE: str = "binance"
    DEFAULT_SYMBOLS: List[str] = list(DEFAULT_AGENT_SYMBOLS)
    PAPER_TRADING: bool = False  # True=가상 체결만 (개발용). 실거래는 False + API 키 필수
    PAPER_TRADING_BALANCE: float = 10000.0  # 페이퍼 모드 가상 USDT
    # True: 리스크 통과 후에도 대시보드에서 승인할 때만 체결
    MANUAL_ORDER_APPROVAL: bool = True
    # 주문 실행: orderbook=호가 최유리 지정가(매수 bid·매도 ask, 대기) | market=시장가
    ORDER_EXECUTION_MODE: str = "orderbook"
    ORDER_FILL_MAX_WAIT_SEC: int = 120
    ORDER_FILL_POLL_INTERVAL_SEC: float = 1.5
    # True: 서버 기동 시 TRX 전량→USDT 매도 시도(없으면 스킵) + 전 에이전트 가동 보장
    STARTUP_BOOTSTRAP_TRADING: bool = True

    # 에이전트 설정
    MARKET_ANALYZER_INTERVAL: int = 60  # 초
    PORTFOLIO_UPDATE_INTERVAL: int = 60  # 초

    # 리스크 기본 설정
    MAX_POSITION_SIZE_PCT: float = 6.0   # %R 스윙에 맞춘 단일 포지션 상한
    MAX_OPEN_POSITIONS: int = 6
    DAILY_LOSS_LIMIT_PCT: float = 4.0
    DEFAULT_STOP_LOSS_PCT: float = 2.4
    # 테이커 왕복 ~0.2% + 슬리피지 여유 — 순익 목표가 수수료보다 크도록
    DEFAULT_TAKE_PROFIT_PCT: float = 6.5
    # 매수 시 명목가 상한: 수수료·슬리피지 여유 (실거래 free 쿼트 기준)
    CASH_FEE_RESERVE_PCT: float = 0.35
    # 거래소 limits.cost.min 미제공 시 최소 주문 USDT(명목) 하한
    ORDER_MIN_NOTIONAL_FALLBACK_USD: float = 5.0

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
            if not v:
                return list(DEFAULT_AGENT_SYMBOLS)
            # JSON 배열 형식 처리: ["a","b"]
            if v.startswith("["):
                import json
                parsed = json.loads(v)
                return parsed if parsed else list(DEFAULT_AGENT_SYMBOLS)
            # 쉼표 구분 문자열 처리: a,b
            out = [s.strip() for s in v.split(",") if s.strip()]
            return out if out else list(DEFAULT_AGENT_SYMBOLS)
        if isinstance(v, list) and len(v) == 0:
            return list(DEFAULT_AGENT_SYMBOLS)
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # NEXT_PUBLIC_* 등 불필요한 환경변수 무시


# 전역 설정 인스턴스
settings = Settings()
