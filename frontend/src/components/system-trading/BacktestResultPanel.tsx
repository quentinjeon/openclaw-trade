'use client'
/**
 * 백테스트 결과 패널
 * 통계 수치 + 신호 목록 표시
 */
import { TrendingUp, TrendingDown, BarChart2, Target, AlertTriangle, Activity } from 'lucide-react'
import type { BacktestResult, TradeSignal } from '@/types/system_trading'
import { formatUSD } from '@/lib/utils'

interface BacktestResultPanelProps {
  result: BacktestResult
  symbol: string
  timeframe: string
}

function StatCard({ label, value, sub, color = 'default' }: {
  label: string
  value: string
  sub?: string
  color?: 'green' | 'red' | 'blue' | 'default'
}) {
  const colorMap = {
    green: 'text-green-400',
    red: 'text-red-400',
    blue: 'text-blue-400',
    default: 'text-slate-100',
  }
  return (
    <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3">
      <p className="text-[10px] text-slate-500 mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono ${colorMap[color]}`}>{value}</p>
      {sub && <p className="text-[10px] text-slate-600 mt-0.5">{sub}</p>}
    </div>
  )
}

export function BacktestResultPanel({ result, symbol, timeframe }: BacktestResultPanelProps) {
  const { stats, signals } = result

  const timeframeLabel: Record<string, string> = {
    '1m': '1분봉', '5m': '5분봉', '15m': '15분봉',
    '1h': '1시간봉', '4h': '4시간봉', '1d': '일봉',
  }

  const buySignals = signals.filter(s => s.type === 'BUY')
  const sellSignals = signals.filter(s => s.type === 'SELL')

  return (
    <div className="bg-slate-900 border-t border-slate-700 p-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <BarChart2 size={14} className="text-blue-400" />
            백테스트 결과
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {symbol} | {timeframeLabel[timeframe] || timeframe} | 최근 {result.candle_count}봉
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="flex items-center gap-1 text-green-400">
            <span className="w-2 h-2 bg-green-500 rounded-full inline-block" />
            매수 {buySignals.length}건
          </span>
          <span className="flex items-center gap-1 text-red-400">
            <span className="w-2 h-2 bg-red-500 rounded-full inline-block" />
            매도 {sellSignals.length}건
          </span>
        </div>
      </div>

      {stats.total_trades === 0 ? (
        <div className="flex items-center gap-2 text-slate-500 py-4">
          <AlertTriangle size={16} />
          <p className="text-sm">해당 기간에 완료된 거래가 없습니다. 조건을 확인해주세요.</p>
        </div>
      ) : (
        <>
          {/* 통계 그리드 */}
          <div className="grid grid-cols-7 gap-2 mb-4">
            <StatCard
              label="총 거래"
              value={`${stats.total_trades}건`}
              sub={`승 ${stats.winning_trades} / 패 ${stats.losing_trades}`}
            />
            <StatCard
              label="승률"
              value={`${stats.win_rate}%`}
              color={stats.win_rate >= 50 ? 'green' : 'red'}
            />
            <StatCard
              label="평균 수익"
              value={`${stats.avg_return_pct >= 0 ? '+' : ''}${stats.avg_return_pct}%`}
              color={stats.avg_return_pct >= 0 ? 'green' : 'red'}
            />
            <StatCard
              label="총 수익률"
              value={`${stats.total_return_pct >= 0 ? '+' : ''}${stats.total_return_pct}%`}
              color={stats.total_return_pct >= 0 ? 'green' : 'red'}
              sub="복리 기준"
            />
            <StatCard
              label="최고 수익"
              value={`+${stats.max_return_pct}%`}
              color="green"
            />
            <StatCard
              label="최대 손실"
              value={`${stats.max_loss_pct}%`}
              color="red"
            />
            <StatCard
              label="최대 낙폭 (MDD)"
              value={`${stats.max_drawdown_pct}%`}
              color="red"
              sub={`평균 ${stats.avg_holding_bars}봉 보유`}
            />
          </div>

          {/* 주의 문구 */}
          <p className="text-[10px] text-slate-600 bg-slate-800/40 rounded-lg px-3 py-2 border border-slate-700/50">
            ⚠️ 백테스트 결과는 과거 데이터 기반이며 미래 수익을 보장하지 않습니다.
            수수료 0.1% 양방향이 적용됐으며, 슬리피지는 미반영됩니다.
          </p>
        </>
      )}
    </div>
  )
}
