'use client'
/**
 * 백테스트 기반 단기 진입 기회 카드
 * 조건 불만족 시 목록 비어 있음 → 카드 자동 숨김
 */
import { useState } from 'react'
import useSWR from 'swr'
import { TrendingUp, Loader2, Zap } from 'lucide-react'
import { pipelineApi } from '@/services/api'
import type { PipelineOpportunity } from '@/types/pipeline'
import { formatDateTimeFull } from '@/lib/utils'

export function PipelineOpportunityCards() {
  const [activating, setActivating] = useState<string | null>(null)
  const { data: oppData, error: oppErr, mutate: mutateOpp, isLoading } = useSWR(
    'pipeline-opportunities',
    () => pipelineApi.getOpportunities(),
    { refreshInterval: 25000, revalidateOnFocus: true },
  )
  const { data: activeData, mutate: mutateActive } = useSWR(
    'pipeline-active',
    () => pipelineApi.getActive(),
    { refreshInterval: 8000 },
  )

  const opps = oppData?.opportunities ?? []
  const active = activeData?.active

  const onActivate = async (o: PipelineOpportunity) => {
    setActivating(o.pipeline_id)
    try {
      await pipelineApi.activate(o.symbol, o.strategy_key)
      await mutateActive()
      await mutateOpp()
    } catch (e) {
      alert(e instanceof Error ? e.message : '활성화 실패 (기회가 만료되었을 수 있습니다)')
      await mutateOpp()
    } finally {
      setActivating(null)
    }
  }

  const onDeactivate = async () => {
    await pipelineApi.deactivate()
    await mutateActive()
  }

  if (oppErr && !oppData && !active) {
    return null
  }

  if (isLoading && opps.length === 0 && !active) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm py-4">
        <Loader2 className="animate-spin" size={16} />
        파이프라인 기회 분석 중…
      </div>
    )
  }

  if (opps.length === 0 && !active) {
    return null
  }

  return (
    <div className="rounded-xl border border-cyan-500/25 bg-cyan-950/15 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-cyan-500/20 bg-cyan-950/25">
        <TrendingUp className="text-cyan-400" size={18} />
        <h2 className="font-semibold text-cyan-100 text-sm">백테스트 기반 단기 파이프라인</h2>
        <span className="text-[10px] text-cyan-500/80">
          (5분봉·과거 유사 신호 기준 추정, 수익 보장 아님)
        </span>
      </div>

      {active && (
        <div className="mx-3 mt-3 mb-2 flex flex-wrap items-center justify-between gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
          <div className="text-sm text-emerald-200">
            <Zap className="inline mr-1 text-emerald-400" size={14} />
            <strong>{active.symbol}</strong> 파이프라인 실행 중 — 이 심볼{' '}
            <strong>매수는 자동 체결</strong> (~{formatDateTimeFull(active.valid_until)} 한국시간까지)
          </div>
          <button
            type="button"
            onClick={onDeactivate}
            className="text-xs px-2 py-1 rounded border border-slate-600 text-slate-400 hover:bg-slate-800"
          >
            종료
          </button>
        </div>
      )}

      <div className="p-3 space-y-3">
        {opps.map((o) => (
          <div
            key={o.pipeline_id}
            className="rounded-lg border border-slate-700 bg-slate-900/50 p-4 space-y-3"
          >
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-lg font-mono font-bold text-slate-100">{o.symbol}</span>
              <span className="text-cyan-400 font-semibold">
                약 {o.window_minutes}분 내 진입 가정 시
              </span>
            </div>
            <p className="text-2xl font-bold text-amber-300">
              과거 유사 구간{' '}
              <span className="text-white">{o.hit_probability_pct.toFixed(0)}%</span> 확률로{' '}
              <span className="text-emerald-400">+{o.target_return_pct}%</span> 이상(고가 기준)
            </p>
            <p className="text-xs text-slate-500">
              표본 {o.sample_size}건 · 평균 최대 변동 +{o.avg_max_gain_pct.toFixed(1)}% · 전략{' '}
              {o.strategy_key}
            </p>
            <p className="text-sm text-slate-400 leading-relaxed">{o.summary}</p>
            <button
              type="button"
              disabled={!!activating}
              onClick={() => onActivate(o)}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium disabled:opacity-50"
            >
              {activating === o.pipeline_id ? (
                <Loader2 className="animate-spin" size={16} />
              ) : (
                <Zap size={16} />
              )}
              이 파이프라인으로 매매 (자동 매수)
            </button>
            <p className="text-[10px] text-slate-600">
              버튼은 현재 봉에서 매수 조건이 맞고 백테스트 기준을 만족할 때만 표시됩니다.
            </p>
          </div>
        ))}
      </div>

      {opps.length === 0 && active && (
        <p className="px-4 pb-3 text-xs text-slate-500">
          새 기회는 조건 충족 시 다시 나타납니다. 위에서 파이프라인을 종료할 수 있습니다.
        </p>
      )}
    </div>
  )
}
