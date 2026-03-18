export interface TradingScoreSymbol {
  symbol: string
  buy_score: number
  sell_score: number
  hold_score: number
  recommended_action: 'BUY' | 'SELL' | 'HOLD'
  has_position: boolean
  suggested_position_pct_of_max: number
  alloc_mult?: number
  breakdown?: Record<string, unknown>
}

export interface TradingScoresResponse {
  symbols: TradingScoreSymbol[]
  portfolio_mix: {
    target_deploy_pct: number
    suggested_cash_pct: number
    avg_opportunity_buy_score?: number
    open_positions_count?: number
    summary: string
  }
  meta: {
    symbol_count: number
    updated_at: string | null
  }
}
