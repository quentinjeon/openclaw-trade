"""
시황 분석 API 라우터
GET /api/market/overview          - BTC/ETH 현재가 + 지표 요약
GET /api/market/ticker/{symbol}   - 개별 심볼 시세
GET /api/market/candles/{symbol}  - OHLCV 캔들 데이터
GET /api/market/watchlist         - 워치리스트 (여러 심볼 시세)
GET /api/market/fx                - USD/KRW 환율 (frankfurter.app, 5분 캐시)
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from loguru import logger
import httpx

from core.symbol_lists import WATCHLIST_SYMBOLS

router = APIRouter(prefix="/api/market", tags=["market"])


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────

class TickerInfo(BaseModel):
    symbol: str
    price: float
    change_24h: float          # 24시간 변화율 (%)
    high_24h: float
    low_24h: float
    volume_24h: float
    direction: str             # BULLISH | BEARISH | NEUTRAL
    confidence: float          # 0.0 ~ 1.0
    indicators: dict
    updated_at: str


class MarketOverview(BaseModel):
    tickers: List[TickerInfo]
    fetched_at: str            # KST 기준 ISO 문자열


class Candle(BaseModel):
    time: int       # Unix timestamp (초)
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleResponse(BaseModel):
    symbol: str
    timeframe: str
    candles: List[Candle]


class WatchlistItem(BaseModel):
    symbol: str
    price: float
    change_24h: float


class WatchlistResponse(BaseModel):
    coins: List[WatchlistItem]
    fetched_at: str


# ──────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────

@router.get("/overview", response_model=MarketOverview)
async def get_market_overview():
    """
    BTC/USDT, ETH/USDT 현재가 + MarketAnalyzer 분석 결과 반환
    market_analyzer_agent의 캐시된 최신 신호를 활용
    """
    from main import market_analyzer_agent, exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(status_code=503, detail="거래소 연결이 초기화되지 않았습니다.")

    symbols = WATCHLIST_SYMBOLS[:8]
    tickers: List[TickerInfo] = []

    for symbol in symbols:
        try:
            # 현재 시세 조회
            ticker = await exchange.fetch_ticker(symbol)

            # MarketAnalyzer의 캐시된 신호 가져오기
            direction = "NEUTRAL"
            confidence = 0.5
            indicators: dict = {}

            if market_analyzer_agent and hasattr(market_analyzer_agent, "latest_signals"):
                cached = market_analyzer_agent.latest_signals.get(symbol)
                if cached:
                    direction = cached.direction
                    confidence = cached.confidence
                    indicators = cached.indicators

            price = float(ticker.get("last", 0))
            change_pct = float(ticker.get("percentage", 0) or 0)
            high_24h = float(ticker.get("high", 0) or 0)
            low_24h = float(ticker.get("low", 0) or 0)
            volume_24h = float(ticker.get("quoteVolume", 0) or 0)

            tickers.append(TickerInfo(
                symbol=symbol,
                price=price,
                change_24h=round(change_pct, 2),
                high_24h=high_24h,
                low_24h=low_24h,
                volume_24h=volume_24h,
                direction=direction,
                confidence=round(confidence, 4),
                indicators=indicators,
                updated_at=datetime.utcnow().isoformat(),
            ))

        except Exception as e:
            logger.error(f"시황 조회 오류 ({symbol}): {e}")
            # 오류 시 기본값으로 채움
            tickers.append(TickerInfo(
                symbol=symbol,
                price=0.0,
                change_24h=0.0,
                high_24h=0.0,
                low_24h=0.0,
                volume_24h=0.0,
                direction="NEUTRAL",
                confidence=0.0,
                indicators={},
                updated_at=datetime.utcnow().isoformat(),
            ))

    return MarketOverview(
        tickers=tickers,
        fetched_at=datetime.utcnow().isoformat(),
    )


@router.get("/ticker/{symbol:path}", response_model=TickerInfo)
async def get_ticker(symbol: str):
    """
    단일 심볼 시세 조회
    예: GET /api/market/ticker/BTC%2FUSDT
    """
    from main import market_analyzer_agent, exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(status_code=503, detail="거래소 연결이 초기화되지 않았습니다.")

    try:
        ticker = await exchange.fetch_ticker(symbol)

        direction = "NEUTRAL"
        confidence = 0.5
        indicators: dict = {}

        if market_analyzer_agent and hasattr(market_analyzer_agent, "latest_signals"):
            cached = market_analyzer_agent.latest_signals.get(symbol)
            if cached:
                direction = cached.direction
                confidence = cached.confidence
                indicators = cached.indicators

        return TickerInfo(
            symbol=symbol,
            price=float(ticker.get("last", 0)),
            change_24h=round(float(ticker.get("percentage", 0) or 0), 2),
            high_24h=float(ticker.get("high", 0) or 0),
            low_24h=float(ticker.get("low", 0) or 0),
            volume_24h=float(ticker.get("quoteVolume", 0) or 0),
            direction=direction,
            confidence=round(confidence, 4),
            indicators=indicators,
            updated_at=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"시세 조회 오류 ({symbol}): {e}")
        raise HTTPException(status_code=500, detail=f"시세 조회 실패: {str(e)}")


# ──────────────────────────────────────────────
# 캔들 데이터 엔드포인트
# ──────────────────────────────────────────────

VALID_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}

@router.get("/candles/{symbol:path}", response_model=CandleResponse)
async def get_candles(
    symbol: str,
    timeframe: str = Query(default="1h", description="캔들 타임프레임 (1m,5m,15m,1h,4h,1d)"),
    limit: int = Query(default=300, ge=10, le=1000, description="캔들 수"),
):
    """
    OHLCV 캔들 데이터 조회
    예: GET /api/market/candles/BTC%2FUSDT?timeframe=1h&limit=300
    """
    from main import exchange

    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 타임프레임: {timeframe}. 가능: {VALID_TIMEFRAMES}")

    if exchange is None or not exchange.is_connected:
        raise HTTPException(status_code=503, detail="거래소 연결이 초기화되지 않았습니다.")

    try:
        # ccxt fetch_ohlcv: [[timestamp_ms, open, high, low, close, volume], ...]
        raw = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

        candles = [
            Candle(
                time=int(bar[0] / 1000),  # ms → 초
                open=bar[1],
                high=bar[2],
                low=bar[3],
                close=bar[4],
                volume=bar[5],
            )
            for bar in raw
        ]

        return CandleResponse(symbol=symbol, timeframe=timeframe, candles=candles)

    except Exception as e:
        logger.error(f"캔들 조회 오류 ({symbol}/{timeframe}): {e}")
        raise HTTPException(status_code=500, detail=f"캔들 조회 실패: {str(e)}")


# ──────────────────────────────────────────────
# 워치리스트 엔드포인트
# ──────────────────────────────────────────────

@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist():
    """
    워치리스트 여러 코인 현재 시세 한번에 조회
    GET /api/market/watchlist
    """
    from main import exchange

    if exchange is None or not exchange.is_connected:
        raise HTTPException(status_code=503, detail="거래소 연결이 초기화되지 않았습니다.")

    coins: List[WatchlistItem] = []
    for sym in WATCHLIST_SYMBOLS:
        try:
            t = await exchange.fetch_ticker(sym)
            coins.append(WatchlistItem(
                symbol=sym,
                price=t.get("last") or t.get("close") or 0.0,
                change_24h=t.get("percentage") or 0.0,
            ))
        except Exception as e:
            logger.warning(f"워치리스트 {sym} 조회 실패: {e}")
            coins.append(WatchlistItem(symbol=sym, price=0.0, change_24h=0.0))

    return WatchlistResponse(coins=coins, fetched_at=datetime.utcnow().isoformat())


# ──────────────────────────────────────────────
# USD/KRW 환율 엔드포인트 (5분 캐시)
# ──────────────────────────────────────────────

class FxRateResponse(BaseModel):
    usd_krw: float          # 1 USD = n KRW
    source: str             # 데이터 출처
    cached_at: str          # 캐시 시각 (ISO)


_fx_cache: Optional[FxRateResponse] = None
_fx_cached_at: Optional[datetime] = None
_FX_CACHE_TTL = timedelta(minutes=5)


@router.get("/fx", response_model=FxRateResponse)
async def get_fx_rate():
    """
    USD/KRW 실시간 환율 조회 (frankfurter.app, 5분 캐시)
    GET /api/market/fx
    """
    global _fx_cache, _fx_cached_at

    now = datetime.utcnow()
    if _fx_cache and _fx_cached_at and (now - _fx_cached_at) < _FX_CACHE_TTL:
        return _fx_cache

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.frankfurter.app/latest",
                params={"from": "USD", "to": "KRW"},
            )
            resp.raise_for_status()
            data = resp.json()
            rate = float(data["rates"]["KRW"])

        _fx_cache = FxRateResponse(
            usd_krw=rate,
            source="frankfurter.app",
            cached_at=now.isoformat(),
        )
        _fx_cached_at = now
        logger.info(f"환율 갱신: 1 USD = {rate:,.2f} KRW")
        return _fx_cache

    except Exception as e:
        logger.error(f"환율 조회 실패: {e}")
        # 캐시가 있으면 만료돼도 반환
        if _fx_cache:
            return _fx_cache
        raise HTTPException(status_code=503, detail=f"환율 조회 실패: {str(e)}")
