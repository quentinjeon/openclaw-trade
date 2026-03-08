/**
 * 시스템 트레이딩 타입 정의
 */

// ── 조건 노드 ──────────────────────────────────────
export interface ConditionNode {
  id: string
  indicator_a: string             // "RSI", "MACD", "CLOSE" 등
  params_a: Record<string, number>
  operator: ConditionOperator
  type_b: 'value' | 'indicator'
  value_b?: number                // type_b === 'value'
  indicator_b?: string            // type_b === 'indicator'
  params_b?: Record<string, number>
}

export type ConditionOperator =
  | '<' | '>' | '<=' | '>=' | '==' | '!='
  | 'crosses_above' | 'crosses_below'

export interface ConditionGroup {
  logic: 'AND' | 'OR'
  conditions: ConditionNode[]
}

// ── 조건식 ─────────────────────────────────────────
export interface SystemCondition {
  id: number
  name: string
  description?: string
  symbol: string
  timeframe: string
  buy_conditions?: ConditionGroup
  sell_conditions?: ConditionGroup
  is_active: boolean
  created_at: string
  updated_at: string
  backtest_win_rate?: number
  backtest_total_trades?: number
  backtest_avg_return?: number
  backtest_max_drawdown?: number
}

export interface ConditionCreate {
  name: string
  description?: string
  symbol: string
  timeframe: string
  buy_conditions?: ConditionGroup
  sell_conditions?: ConditionGroup
  is_active?: boolean
}

// ── 백테스트 ───────────────────────────────────────
export interface TradeSignal {
  time: number                   // Unix timestamp (초)
  type: 'BUY' | 'SELL'
  price: number
  return_pct?: number
  triggered_conditions: string[]
}

export interface BacktestStats {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number               // %
  avg_return_pct: number         // %
  total_return_pct: number       // %
  max_return_pct: number         // %
  max_loss_pct: number           // %
  max_drawdown_pct: number       // %
  avg_holding_bars: number
}

export interface BacktestResult {
  signals: TradeSignal[]
  stats: BacktestStats
  candle_count: number
}

// ── Text-to-Rule ────────────────────────────────────
export interface TextToRuleResponse {
  success: boolean
  group?: ConditionGroup
  explanation: string
  method: 'pattern' | 'llm' | 'failed'
}

// ── 전략 템플릿 ────────────────────────────────────
export interface StrategyTemplate {
  key: string
  name: string
  description: string
  buy_group: ConditionGroup
  sell_group: ConditionGroup
}

// ── 지표 목록 (UI 선택용) ────────────────────────────
export const INDICATOR_OPTIONS = [
  // 가격
  { value: 'CLOSE', label: '종가 (CLOSE)', params: [] },
  { value: 'OPEN', label: '시가 (OPEN)', params: [] },
  { value: 'HIGH', label: '고가 (HIGH)', params: [] },
  { value: 'LOW', label: '저가 (LOW)', params: [] },
  { value: 'VOLUME', label: '거래량 (VOLUME)', params: [] },
  // 이동평균
  { value: 'MA', label: '단순이동평균 (MA)', params: [{ key: 'period', label: '기간', default: 20 }] },
  { value: 'EMA', label: '지수이동평균 (EMA)', params: [{ key: 'period', label: '기간', default: 20 }] },
  // 오실레이터
  { value: 'RSI', label: 'RSI', params: [{ key: 'period', label: '기간', default: 14 }] },
  { value: 'STOCH_K', label: '스토캐스틱 %K', params: [{ key: 'k_period', label: 'K기간', default: 14 }, { key: 'd_period', label: 'D기간', default: 3 }] },
  { value: 'STOCH_D', label: '스토캐스틱 %D', params: [{ key: 'k_period', label: 'K기간', default: 14 }, { key: 'd_period', label: 'D기간', default: 3 }] },
  // 추세
  { value: 'MACD', label: 'MACD 라인', params: [{ key: 'fast', label: 'Fast', default: 12 }, { key: 'slow', label: 'Slow', default: 26 }, { key: 'signal', label: 'Signal', default: 9 }] },
  { value: 'MACD_SIGNAL', label: 'MACD 시그널', params: [{ key: 'fast', label: 'Fast', default: 12 }, { key: 'slow', label: 'Slow', default: 26 }, { key: 'signal', label: 'Signal', default: 9 }] },
  { value: 'MACD_HIST', label: 'MACD 히스토그램', params: [{ key: 'fast', label: 'Fast', default: 12 }, { key: 'slow', label: 'Slow', default: 26 }, { key: 'signal', label: 'Signal', default: 9 }] },
  // 볼린저
  { value: 'BB_UPPER', label: '볼린저밴드 상단', params: [{ key: 'period', label: '기간', default: 20 }, { key: 'std_dev', label: '표준편차', default: 2 }] },
  { value: 'BB_MIDDLE', label: '볼린저밴드 중간', params: [{ key: 'period', label: '기간', default: 20 }] },
  { value: 'BB_LOWER', label: '볼린저밴드 하단', params: [{ key: 'period', label: '기간', default: 20 }, { key: 'std_dev', label: '표준편차', default: 2 }] },
  // 파생
  { value: 'VOLUME_RATIO', label: '거래량 비율 (평균대비)', params: [{ key: 'period', label: '기간', default: 20 }] },
  { value: 'PRICE_CHANGE', label: '가격변화율(%)', params: [{ key: 'period', label: '봉 수', default: 1 }] },
  { value: 'ATR', label: 'ATR (평균진폭)', params: [{ key: 'period', label: '기간', default: 14 }] },
] as const

export const OPERATOR_OPTIONS = [
  { value: '<', label: '< 미만' },
  { value: '<=', label: '≤ 이하' },
  { value: '>', label: '> 초과' },
  { value: '>=', label: '≥ 이상' },
  { value: '==', label: '= 같음' },
  { value: 'crosses_above', label: '↑ 상향돌파 (골든크로스)' },
  { value: 'crosses_below', label: '↓ 하향돌파 (데드크로스)' },
] as const

export const TIMEFRAME_OPTIONS = [
  { value: '1m', label: '1분' },
  { value: '5m', label: '5분' },
  { value: '15m', label: '15분' },
  { value: '1h', label: '1시간' },
  { value: '4h', label: '4시간' },
  { value: '1d', label: '일봉' },
]

export const SYMBOL_OPTIONS = [
  'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
  'ADA/USDT', 'DOGE/USDT', 'MATIC/USDT', 'DOT/USDT', 'LINK/USDT',
]
