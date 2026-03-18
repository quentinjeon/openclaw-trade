export interface PipelineOpportunity {
  pipeline_id: string
  symbol: string
  timeframe: string
  window_minutes: number
  horizon_bars: number
  target_return_pct: number
  hit_probability_pct: number
  sample_size: number
  avg_max_gain_pct: number
  live_valid: boolean
  valid_until: string
  strategy_key: string
  summary: string
}

export interface PipelineOpportunitiesResponse {
  opportunities: PipelineOpportunity[]
  computed_at: string
}

export interface ActivePipeline {
  symbol: string
  strategy_key: string
  label: string
  valid_until: string
  pipeline_id: string
}
