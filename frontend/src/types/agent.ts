/**
 * 에이전트 관련 타입 정의
 */

export type AgentStatus = 'IDLE' | 'RUNNING' | 'ANALYZING' | 'EXECUTING' | 'ERROR' | 'STOPPED'

export type AgentType =
  | 'market_analyzer'
  | 'strategy'
  | 'risk_manager'
  | 'execution'
  | 'portfolio'

export interface Agent {
  agent_id: string
  agent_type: AgentType
  status: AgentStatus
  total_cycles: number
  error_count: number
  last_run: string | null
  started_at: string | null
  is_running: boolean
}

export interface AgentLog {
  id: number
  agent_id: string
  agent_type: AgentType
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DECISION' | 'SIGNAL'
  message: string
  data?: string
  created_at: string
}

export interface MarketSignal {
  symbol: string
  exchange: string
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  confidence: number
  indicators: Record<string, number>
  price: number
  volume_24h: number
  timestamp: string
}

export interface StrategyConfig {
  name: string
  enabled: boolean
  params: Record<string, number>
  description?: string
}

export interface RiskConfig {
  max_position_size_pct: number
  max_open_positions: number
  daily_loss_limit_pct: number
  stop_loss_pct: number
  take_profit_pct: number
}

export interface SystemSettings {
  paper_trading: boolean
  default_exchange: string
  default_symbols: string[]
  risk: RiskConfig
  strategies: StrategyConfig[]
}
