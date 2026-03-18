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
  /** 봇이 진입·추적 중인 포지션 */
  managed_by_bot?: boolean
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
  /** 실거래: 거래소 현물 잔고 동기화 */
  live_trading?: boolean
  data_source?: 'exchange' | 'simulated'
}
