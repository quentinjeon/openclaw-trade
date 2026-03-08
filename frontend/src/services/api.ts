/**
 * API 클라이언트
 * 모든 백엔드 API 호출은 이 모듈을 통해서만 수행합니다.
 */
import type { Portfolio } from '@/types/portfolio'
import type { Agent, AgentLog, RiskConfig, StrategyConfig, SystemSettings } from '@/types/agent'
import type { Trade, TradeListResponse } from '@/types/trade'
import type { MarketOverview, TickerInfo, CandleResponse, WatchlistResponse, FxRateResponse } from '@/types/market'

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
