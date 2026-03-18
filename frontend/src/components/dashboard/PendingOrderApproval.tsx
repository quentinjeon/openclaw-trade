'use client'
/**
 * 리스크 통과 주문 수동 승인 패널
 */
import { useEffect, useState, useCallback } from 'react'
import useSWR from 'swr'
import { Check, X, Shield, Zap } from 'lucide-react'
import { fetcher } from '@/services/api'
import { formatDateTime } from '@/lib/utils'
import { useWebSocket } from '@/hooks/useWebSocket'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002'

export interface PendingOrderRow {
  id: string
  symbol: string
  side: string
  amount: number
  stop_loss: number
  take_profit: number
  position_size_pct: number
  reasoning: string
  strategy_name: string
  confidence: number
  created_at: string
}

interface PendingListResponse {
  manual_mode: boolean
  pending: PendingOrderRow[]
  count?: number
  message?: string
}

export function PendingOrderApproval() {
  const [busy, setBusy] = useState<string | null>(null)
  const { data, mutate, isLoading } = useSWR<PendingListResponse>(
    `${API}/api/pending-orders/`,
    fetcher,
    { refreshInterval: 4000 },
  )

  const { lastMessage } = useWebSocket<Record<string, unknown>>('pending-orders')

  const refresh = useCallback(() => {
    mutate()
  }, [mutate])

  useEffect(() => {
    const m = lastMessage as unknown as { type?: string } | null
    if (m?.type === 'new_pending' || m?.type === 'removed' || m?.type === 'snapshot') {
      mutate()
    }
  }, [lastMessage, mutate])

  const [modeOn, setModeOn] = useState(true)
  const [modeLoading, setModeLoading] = useState(false)

  useEffect(() => {
    if (data?.manual_mode !== undefined) setModeOn(data.manual_mode)
  }, [data?.manual_mode])

  const toggleMode = async () => {
    setModeLoading(true)
    try {
      const res = await fetch(`${API}/api/settings/order-approval`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !modeOn }),
      })
      if (res.ok) {
        const j = await res.json()
        setModeOn(!!j.manual_order_approval)
        mutate()
      }
    } finally {
      setModeLoading(false)
    }
  }

  const approve = async (id: string) => {
    setBusy(id)
    try {
      const res = await fetch(`${API}/api/pending-orders/${id}/approve`, { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      await mutate()
    } catch (e) {
      console.error(e)
      alert('승인 실패: ' + (e instanceof Error ? e.message : ''))
    } finally {
      setBusy(null)
    }
  }

  const reject = async (id: string) => {
    setBusy(id)
    try {
      await fetch(`${API}/api/pending-orders/${id}/reject`, { method: 'POST' })
      await mutate()
    } finally {
      setBusy(null)
    }
  }

  const pending = data?.pending ?? []

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-amber-500/20 bg-amber-950/30">
        <div className="flex items-center gap-2">
          <Shield className="text-amber-400" size={20} />
          <h2 className="font-semibold text-amber-100">주문 승인</h2>
          <span className="text-xs text-amber-400/80">
            {modeOn ? '수동 승인 모드' : '즉시 체결 모드'}
          </span>
        </div>
        <button
          type="button"
          onClick={toggleMode}
          disabled={modeLoading}
          className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
            modeOn
              ? 'border-amber-500/50 text-amber-300 hover:bg-amber-500/10'
              : 'border-slate-600 text-slate-400 hover:bg-slate-800'
          }`}
        >
          {modeLoading ? '…' : modeOn ? '자동 체결로 전환' : '수동 승인으로 전환'}
        </button>
      </div>

      {!modeOn && (
        <p className="px-4 py-3 text-sm text-slate-500">
          수동 승인이 꺼져 있으면 리스크 통과 주문이 바로 체결됩니다.
        </p>
      )}

      {modeOn && pending.length === 0 && !isLoading && (
        <p className="px-4 py-6 text-sm text-slate-500 text-center">
          대기 중인 주문이 없습니다. 신호가 나오면 여기에 표시됩니다.
        </p>
      )}

      {modeOn && pending.length > 0 && (
        <ul className="divide-y divide-slate-800">
          {pending.map((o) => (
            <li key={o.id} className="p-4 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono font-semibold text-slate-100">{o.symbol}</span>
                <span
                  className={
                    o.side === 'buy'
                      ? 'text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400'
                      : 'text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400'
                  }
                >
                  {o.side.toUpperCase()}
                </span>
                <span className="text-sm text-slate-400">
                  {o.amount.toFixed(6)} · 손절 {o.stop_loss} / 익절 {o.take_profit}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                {formatDateTime(o.created_at)} (KST) · {o.strategy_name} · 신뢰도{' '}
                {(o.confidence * 100).toFixed(0)}%
              </p>
              <p className="text-sm text-slate-300 line-clamp-2">{o.reasoning}</p>
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  disabled={busy === o.id}
                  onClick={() => approve(o.id)}
                  className="flex items-center gap-1 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm disabled:opacity-50"
                >
                  <Check size={16} />
                  승인 후 체결
                </button>
                <button
                  type="button"
                  disabled={busy === o.id}
                  onClick={() => reject(o.id)}
                  className="flex items-center gap-1 px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-800 text-sm"
                >
                  <X size={16} />
                  거부
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {modeOn && (
        <button
          type="button"
          onClick={refresh}
          className="w-full py-2 text-xs text-slate-500 hover:text-slate-400 flex items-center justify-center gap-1"
        >
          <Zap size={12} /> 새로고침
        </button>
      )}
    </div>
  )
}
