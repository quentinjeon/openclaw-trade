/** REST 주문 API 응답 */

export interface OrderConstraints {
  symbol: string
  base?: string
  quote?: string
  amount_min?: number
  amount_max?: number
  cost_min?: number
  price_min?: number
  amount_precision?: number
  price_precision?: number
}

export interface PlacedOrder {
  id: string
  symbol?: string
  side?: string
  type?: string
  amount?: number
  filled?: number
  price?: number
  average?: number
  status?: string
  cost?: number
}

export interface OrderPlaceResponse {
  success: boolean
  order: PlacedOrder
}

export interface SellAllFreeResponse extends OrderPlaceResponse {
  sold_base_amount: number
}

export interface OpenOrdersResponse {
  count: number
  orders: PlacedOrder[]
}

export interface ExchangeTradeRow {
  id?: string
  order?: string
  symbol?: string
  side?: string
  amount?: number
  price?: number
  cost?: number
  fee?: unknown
  timestamp?: number
}
