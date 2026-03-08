/**
 * 시황 관련 타입 정의
 */

export interface TickerInfo {
  symbol: string
  price: number
  change_24h: number       // 24시간 변화율 (%)
  high_24h: number
  low_24h: number
  volume_24h: number
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  confidence: number       // 0.0 ~ 1.0
  indicators: {
    rsi?: number
    macd?: number
    macd_signal?: number
    macd_diff?: number
    bb_upper?: number
    bb_lower?: number
    bb_middle?: number
    ma20?: number
    ma50?: number
    ma200?: number
    price?: number
    volume_ratio?: number
  }
  updated_at: string
}

export interface MarketOverview {
  tickers: TickerInfo[]
  fetched_at: string
}

export interface Candle {
  time: number   // Unix timestamp (초)
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface CandleResponse {
  symbol: string
  timeframe: string
  candles: Candle[]
}

export interface WatchlistItem {
  symbol: string
  price: number
  change_24h: number
}

export interface WatchlistResponse {
  coins: WatchlistItem[]
  fetched_at: string
}

export interface FxRateResponse {
  usd_krw: number   // 1 USD = n KRW
  source: string
  cached_at: string
}
