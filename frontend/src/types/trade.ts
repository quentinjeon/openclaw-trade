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
  agent_id?: string | null
  strategy?: string
  stop_loss?: number
  take_profit?: number
  /** 매도 체결 시 청산가 */
  close_price?: number | null
  pnl?: number
  created_at: string
  updated_at: string
}

export interface TradeListResponse {
  trades: Trade[]
  total: number
}
