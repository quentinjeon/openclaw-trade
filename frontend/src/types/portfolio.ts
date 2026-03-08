/**
 * 포트폴리오 관련 타입 정의
 */

export interface Position {
  symbol: string
  amount: number
  entry_price: number
  current_price: number
  unrealized_pnl: number
  stop_loss?: number
  take_profit?: number
}

export interface Portfolio {
  total_value_usd: number
  cash_usd: number
  positions: Record<string, Position>
  pnl_today: number
  pnl_total: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_return_pct: number
  initial_balance: number
  updated_at: string
}
