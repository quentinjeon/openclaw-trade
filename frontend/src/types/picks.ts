export interface PickScannerConfig {
  auto_buy_enabled: boolean
  min_score: number
  template_key: string
  condition_id: number | null
  timeframe: string
  candle_limit: number
  symbols: string[]
  scan_interval_minutes: number
  require_live_buy_signal: boolean
  max_auto_buys_per_scan: number
}

export interface PickResultRow {
  symbol: string
  score: number
  score_detail: string
  win_rate: number
  total_return_pct: number
  max_drawdown_pct: number
  total_trades: number
  avg_return_pct: number
  live_buy_signal: boolean
  template_key: string
}

export interface PickScanResponse {
  count: number
  timeframe: string
  results: PickResultRow[]
}

export interface AutoBuyOnceResponse {
  attempted: boolean
  bought: number
  skipped_reason: string | null
  details: { symbol: string; action: string; reason?: string; score?: number }[]
}
