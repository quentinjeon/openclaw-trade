/**
 * 거래 관련 타입 정의
 */

export interface Trade {
  id: string
  symbol: string
  exchange: string
  side: 'buy' | 'sell'
  type: 'market' | 'limit'
  amount: number
  price: number
  cost: number
  fee: number
  status: 'open' | 'closed' | 'cancelled' | 'filled' | 'failed'
  is_paper: boolean
  strategy?: string
  stop_loss?: number
  take_profit?: number
  pnl?: number
  created_at: string
}

export interface TradeListResponse {
  trades: Trade[]
  total: number
}
