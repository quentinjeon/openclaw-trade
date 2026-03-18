/**
 * API 클라이언트
 * 모든 백엔드 API 호출은 이 모듈을 통해서만 수행합니다.
 */
import type { Portfolio } from '@/types/portfolio'
import type { Agent, AgentLog, RiskConfig, StrategyConfig, SystemSettings } from '@/types/agent'
import type { Trade, TradeListResponse } from '@/types/trade'
import type { MarketOverview, TickerInfo, CandleResponse, WatchlistResponse, FxRateResponse } from '@/types/market'
import type { WalletBalance } from '@/types/wallet'
import type {
  SystemCondition,
  ConditionCreate,
  TextToRuleResponse,
  BacktestResult,
  StrategyTemplate,
  ConditionGroup,
} from '@/types/system_trading'
import type {
  PickScannerConfig,
  PickScanResponse,
  AutoBuyOnceResponse,
} from '@/types/picks'
import type { PipelineOpportunitiesResponse, ActivePipeline } from '@/types/pipeline'
import type {
  OrderConstraints,
  OrderPlaceResponse,
  OpenOrdersResponse,
  SellAllFreeResponse,
  ExchangeTradeRow,
} from '@/types/orders'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002'

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    throw new ApiError(response.status, `API 오류: ${response.status} ${response.statusText}`)
  }

  return response.json() as Promise<T>
}

// ──────────────────────────────────────────────
// 포트폴리오 API
// ──────────────────────────────────────────────
export const portfolioApi = {
  getPortfolio: (): Promise<Portfolio> =>
    fetchJson('/api/portfolio/'),
}

// ──────────────────────────────────────────────
// 거래 API
// ──────────────────────────────────────────────
export const tradeApi = {
  getTrades: (params?: { symbol?: string; limit?: number; offset?: number }): Promise<TradeListResponse> => {
    const query = new URLSearchParams()
    if (params?.symbol) query.set('symbol', params.symbol)
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.offset) query.set('offset', String(params.offset))
    const qs = query.toString() ? `?${query.toString()}` : ''
    return fetchJson(`/api/trades/${qs}`)
  },

  closeAllPositions: (): Promise<{ message: string; success: boolean }> =>
    fetchJson('/api/trades/close-all', { method: 'POST' }),
}

// ──────────────────────────────────────────────
// 에이전트 API
// ──────────────────────────────────────────────
export const agentApi = {
  getAgents: (): Promise<Agent[]> =>
    fetchJson('/api/agents/'),

  getAgentLogs: (params?: {
    agent_type?: string
    level?: string
    limit?: number
  }): Promise<AgentLog[]> => {
    const query = new URLSearchParams()
    if (params?.agent_type) query.set('agent_type', params.agent_type)
    if (params?.level) query.set('level', params.level)
    if (params?.limit) query.set('limit', String(params.limit))
    const qs = query.toString() ? `?${query.toString()}` : ''
    return fetchJson(`/api/agents/logs${qs}`)
  },

  startAgent: (agentType: string): Promise<{ success: boolean; message: string }> =>
    fetchJson(`/api/agents/${agentType}/start`, { method: 'POST' }),

  stopAgent: (agentType: string): Promise<{ success: boolean; message: string }> =>
    fetchJson(`/api/agents/${agentType}/stop`, { method: 'POST' }),

  /** TRX 전량 매도(보유 시) + 자동매매 에이전트 전부 시작 */
  bootstrapAutoTrading: (): Promise<{
    success: boolean
    trx_sell: Record<string, unknown>
    agents_started: string[]
    message: string
  }> => fetchJson('/api/agents/bootstrap-auto-trading', { method: 'POST' }),
}

// ──────────────────────────────────────────────
// 설정 API
// ──────────────────────────────────────────────
export const settingsApi = {
  getSettings: (): Promise<SystemSettings> =>
    fetchJson('/api/settings/'),

  updateRiskSettings: (config: RiskConfig): Promise<{ success: boolean }> =>
    fetchJson('/api/settings/risk', {
      method: 'PUT',
      body: JSON.stringify(config),
    }),

  updateStrategySettings: (
    strategyName: string,
    config: StrategyConfig,
  ): Promise<{ success: boolean }> =>
    fetchJson(`/api/settings/strategies/${strategyName}`, {
      method: 'PUT',
      body: JSON.stringify(config),
    }),
}

// ──────────────────────────────────────────────
// 시황 API
// ──────────────────────────────────────────────
export const marketApi = {
  getOverview: () => fetchJson<MarketOverview>('/api/market/overview'),
  getTicker: (symbol: string) =>
    fetchJson<TickerInfo>(`/api/market/ticker/${encodeURIComponent(symbol)}`),
  getCandles: (symbol: string, timeframe = '1h', limit = 300) =>
    fetchJson<CandleResponse>(
      `/api/market/candles/${encodeURIComponent(symbol)}?timeframe=${timeframe}&limit=${limit}`
    ),
  getWatchlist: () => fetchJson<WatchlistResponse>('/api/market/watchlist'),
  getFxRate: () => fetchJson<FxRateResponse>('/api/market/fx'),
}

// ──────────────────────────────────────────────
// 지갑 API
// ──────────────────────────────────────────────
export const walletApi = {
  getBalance: (): Promise<WalletBalance> =>
    fetchJson('/api/wallet/balance'),
}

// ──────────────────────────────────────────────
// 주문 API (시장가·지정가·호가·미체결·취소)
// ──────────────────────────────────────────────
export const ordersApi = {
  getConstraints: (symbol: string): Promise<OrderConstraints> =>
    fetchJson(`/api/orders/constraints/${encodeURIComponent(symbol)}`),

  market: (body: {
    symbol: string
    side: 'buy' | 'sell'
    amount: number
    track_position?: boolean
  }): Promise<OrderPlaceResponse> =>
    fetchJson('/api/orders/market', { method: 'POST', body: JSON.stringify(body) }),

  limit: (body: {
    symbol: string
    side: 'buy' | 'sell'
    amount: number
    price: number
    wait_for_fill?: boolean
    track_position?: boolean
  }): Promise<OrderPlaceResponse> =>
    fetchJson('/api/orders/limit', { method: 'POST', body: JSON.stringify(body) }),

  orderbook: (body: {
    symbol: string
    side: 'buy' | 'sell'
    amount: number
    aggressive?: boolean
    track_position?: boolean
  }): Promise<OrderPlaceResponse> =>
    fetchJson('/api/orders/orderbook', { method: 'POST', body: JSON.stringify(body) }),

  sellAllFree: (body: {
    symbol: string
    execution?: 'market' | 'orderbook'
    aggressive?: boolean
  }): Promise<SellAllFreeResponse> =>
    fetchJson('/api/orders/sell-all-free', { method: 'POST', body: JSON.stringify(body) }),

  getOpen: (symbol?: string): Promise<OpenOrdersResponse> => {
    const q = symbol ? `?symbol=${encodeURIComponent(symbol)}` : ''
    return fetchJson(`/api/orders/open${q}`)
  },

  getStatus: (orderId: string, symbol: string): Promise<Record<string, unknown>> => {
    const q = new URLSearchParams({ order_id: orderId, symbol })
    return fetchJson(`/api/orders/status?${q}`)
  },

  cancel: (orderId: string, symbol: string): Promise<{ success: boolean; result: unknown }> => {
    const q = new URLSearchParams({ order_id: orderId, symbol })
    return fetchJson(`/api/orders/cancel?${q}`, { method: 'DELETE' })
  },

  cancelAll: (symbol?: string): Promise<{ cancelled: string[]; errors: unknown[]; count: number }> => {
    const q = symbol ? `?symbol=${encodeURIComponent(symbol)}` : ''
    return fetchJson(`/api/orders/cancel-all${q}`, { method: 'POST' })
  },

  exchangeTrades: (symbol: string, limit = 50): Promise<{ symbol: string; trades: ExchangeTradeRow[]; count: number }> => {
    const q = new URLSearchParams({ symbol, limit: String(limit) })
    return fetchJson(`/api/orders/exchange-trades?${q}`)
  },
}

// ──────────────────────────────────────────────
// 시스템 트레이딩 API
// ──────────────────────────────────────────────
export const systemTradingApi = {
  // 조건식 CRUD
  listConditions: (): Promise<SystemCondition[]> =>
    fetchJson('/api/system/conditions'),

  createCondition: (data: ConditionCreate): Promise<SystemCondition> =>
    fetchJson('/api/system/conditions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateCondition: (id: number, data: Partial<ConditionCreate>): Promise<SystemCondition> =>
    fetchJson(`/api/system/conditions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteCondition: (id: number): Promise<{ message: string }> =>
    fetchJson(`/api/system/conditions/${id}`, { method: 'DELETE' }),

  // Text-to-Rule
  textToRule: (text: string, side: 'buy' | 'sell'): Promise<TextToRuleResponse> =>
    fetchJson('/api/system/text-to-rule', {
      method: 'POST',
      body: JSON.stringify({ text, side }),
    }),

  // 전략 템플릿
  getTemplates: (): Promise<{ templates: StrategyTemplate[] }> =>
    fetchJson('/api/system/templates'),

  // 백테스트
  backtest: (params: {
    condition_id?: number
    buy_conditions?: ConditionGroup
    sell_conditions?: ConditionGroup
    symbol: string
    timeframe: string
    limit?: number
  }): Promise<BacktestResult> =>
    fetchJson('/api/system/backtest', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  // 현재 조건 체크
  checkNow: (params: {
    condition_id?: number
    buy_conditions?: ConditionGroup
    sell_conditions?: ConditionGroup
    symbol: string
  }): Promise<{
    triggered: boolean
    side: 'BUY' | 'SELL' | 'HOLD'
    current_values: Record<string, number>
    passed_buy_conditions: string[]
    failed_buy_conditions: string[]
  }> =>
    fetchJson('/api/system/check-now', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
}

// ──────────────────────────────────────────────
// 백테스트 스캐너 (종목 추천·자동매수)
// ──────────────────────────────────────────────
export const picksApi = {
  getConfig: (): Promise<{
    config: PickScannerConfig
    template_options: { key: string; name: string }[]
  }> => fetchJson('/api/picks/config'),

  putConfig: (partial: Partial<PickScannerConfig>): Promise<{ success: boolean; config: PickScannerConfig }> =>
    fetchJson('/api/picks/config', { method: 'PUT', body: JSON.stringify(partial) }),

  scan: (params?: {
    symbols?: string[]
    timeframe?: string
    candle_limit?: number
    template_key?: string
    condition_id?: number | null
  }): Promise<PickScanResponse> =>
    fetchJson('/api/picks/scan', {
      method: 'POST',
      body: JSON.stringify(params || {}),
    }),

  autoBuyOnce: (force?: boolean): Promise<AutoBuyOnceResponse> => {
    const q = force ? '?force=true' : ''
    return fetchJson(`/api/picks/auto-buy-once${q}`, { method: 'POST' })
  },
}

// ──────────────────────────────────────────────
// 백테스트 기반 단기 파이프라인 기회
// ──────────────────────────────────────────────
export const pipelineApi = {
  getOpportunities: (): Promise<PipelineOpportunitiesResponse> =>
    fetchJson('/api/pipeline-opportunities/'),

  getActive: (): Promise<{ active: ActivePipeline | null }> =>
    fetchJson('/api/pipeline-opportunities/active'),

  activate: (symbol: string, strategyKey = 'larry_williams'): Promise<{ success: boolean; active: ActivePipeline }> =>
    fetchJson('/api/pipeline-opportunities/activate', {
      method: 'POST',
      body: JSON.stringify({ symbol, strategy_key: strategyKey }),
    }),

  deactivate: (): Promise<{ success: boolean }> =>
    fetchJson('/api/pipeline-opportunities/deactivate', { method: 'POST' }),
}

// ──────────────────────────────────────────────
// 헬스체크
// ──────────────────────────────────────────────
export const healthApi = {
  check: () => fetchJson<{ status: string; version: string; agents: Record<string, string> }>('/health'),
}

// SWR fetcher - response.json()은 any를 반환하므로 SWR 제네릭과 호환됨
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const fetcher = (url: string): Promise<any> =>
  fetch(url).then((res) => {
    if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`)
    return res.json()
  })

export { ApiError }
