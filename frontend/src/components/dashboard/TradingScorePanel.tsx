'use client'

/**
 * 매수·매도·보유 점수 및 권장 자금 비중 (대시보드)
 */
import useSWR from 'swr'
import { TrendingUp, TrendingDown, Anchor, Wallet, RefreshCw } from 'lucide-react'
import { fetcher } from '@/services/api'
import type { TradingScoresResponse, TradingScoreSymbol } from '@/types/tradingScores'
import { formatDateTimeFull } from '@/lib/utils'

const API = `${process.env.NEXT_PUBLIC_API_URL}/api/trading-scores/`

function ScoreBar({
  label,
  value,
  variant,
  icon: Icon,
}: {
  label: string
  value: number
  variant: 'buy' | 'sell' | 'hold'
  icon: typeof TrendingUp
}) {
  const v = Math.min(100, Math.max(0, value))
  const styles = {
    buy: { text: 'text-emerald-400', bar: 'bg-emerald-500' },
    sell: { text: 'text-rose-400', bar: 'bg-rose-500' },
    hold: { text: 'text-sky-400', bar: 'bg-sky-500' },
  }[variant]
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className={`flex items-center gap-1 ${styles.text}`}>
          <Icon size={12} />
          {label}
        </span>
        <span className="text-slate-300 font-mono">{v.toFixed(0)}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${styles.bar}`}
          style={{ width: `${v}%` }}
        />
      </div>
    </div>
  )
}

function SymbolCard({ row }: { row: TradingScoreSymbol }) {
  const act = row.recommended_action
  const badge =
    act === 'BUY'
      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
      : act === 'SELL'
        ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
        : 'bg-slate-600/30 text-slate-300 border-slate-500/40'

  return (
    <div
      className={`rounded-xl border p-4 space-y-3 ${
        row.has_position ? 'border-amber-500/30 bg-amber-500/5' : 'border-slate-700/80 bg-slate-900/40'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-slate-100">{row.symbol}</div>
          {row.has_position && (
            <span className="text-[10px] uppercase tracking-wide text-amber-400/90">보유 중</span>
          )}
        </div>
        <span className={`text-xs px-2 py-0.5 rounded border shrink-0 ${badge}`}>{act}</span>
      </div>
      <ScoreBar label="매수 매력" value={row.buy_score} variant="buy" icon={TrendingUp} />
      <ScoreBar label="매도 압력" value={row.sell_score} variant="sell" icon={TrendingDown} />
      <ScoreBar label="보유 유지" value={row.hold_score} variant="hold" icon={Anchor} />
      {!row.has_position && act === 'BUY' && (
        <p className="text-[11px] text-slate-400 leading-snug">
          다음 매수 시 최대 허용 포지션 대비 약{' '}
          <span className="text-emerald-300 font-medium">{row.suggested_position_pct_of_max}%</span> 투입
          (점수 기반 비중)
        </p>
      )}
      {row.has_position && (
        <p className="text-[11px] text-slate-400">
          매도 &gt; 보유 유지이면 청산 후보 · 자동매매는 점수·전략 병합 적용
        </p>
      )}
    </div>
  )
}

export function TradingScorePanel({ liveTrading = true }: { liveTrading?: boolean }) {
  const { data, error, isLoading } = useSWR<TradingScoresResponse>(API, fetcher, {
    refreshInterval: 12000,
  })

  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-300">
        매매 점수를 불러오지 못했습니다.
      </div>
    )
  }

  const mix = data?.portfolio_mix
  const symbols = data?.symbols ?? []

  return (
    <div className="rounded-xl border border-slate-700/80 bg-slate-950/50 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/80 bg-slate-900/60">
        <div>
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <Wallet className="text-cyan-400" size={20} />
            매수·매도·보유 점수
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Williams %R · RSI · MACD · 추세 · 시장 방향 합성 → 자금 비중 자동 반영
            {liveTrading && (
              <span className="text-emerald-500/90 block mt-1">
                실계좌 보유 코인 포함 · 매수/매도 체결은 거래소·DB 기록과 연동됩니다.
              </span>
            )}
          </p>
        </div>
        {isLoading && <RefreshCw className="animate-spin text-slate-500" size={18} />}
      </div>

      {mix && (
        <div className="px-4 py-3 bg-gradient-to-r from-cyan-950/40 to-slate-900/40 border-b border-slate-700/60">
          <div className="flex flex-wrap gap-6 items-center">
            <div>
              <div className="text-[10px] uppercase text-slate-500 tracking-wider">권장 투자 비중</div>
              <div className="text-2xl font-bold text-cyan-300">{mix.target_deploy_pct}%</div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-slate-500 tracking-wider">권장 현금 비중</div>
              <div className="text-2xl font-bold text-slate-200">{mix.suggested_cash_pct}%</div>
            </div>
            <div className="flex-1 min-w-[200px] text-sm text-slate-400 leading-relaxed">{mix.summary}</div>
          </div>
          <div className="mt-2 h-2 rounded-full bg-slate-800 flex overflow-hidden">
            <div
              className="bg-cyan-500/70 h-full transition-all"
              style={{ width: `${mix.target_deploy_pct}%` }}
            />
            <div className="bg-slate-600/50 h-full flex-1" />
          </div>
        </div>
      )}

      <div className="p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 max-h-[480px] overflow-y-auto">
        {symbols.length === 0 && !isLoading && (
          <p className="text-slate-500 text-sm col-span-full">점수 데이터 수집 중…</p>
        )}
        {symbols.map((row) => (
          <SymbolCard key={row.symbol} row={row} />
        ))}
      </div>

      {data?.meta?.updated_at && (
        <div className="px-4 py-2 text-[10px] text-slate-600 border-t border-slate-800">
          갱신: {formatDateTimeFull(data.meta.updated_at)} (KST) · 심볼 {data.meta.symbol_count}개
        </div>
      )}
    </div>
  )
}
