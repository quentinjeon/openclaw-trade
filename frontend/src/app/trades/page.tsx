'use client'
/**
 * 거래 내역 페이지
 */
import useSWR from 'swr'
import { TradeHistoryTable } from '@/components/trading/TradeHistoryTable'
import { fetcher } from '@/services/api'
import type { TradeListResponse } from '@/types/trade'

export default function TradesPage() {
  const { data, isLoading } = useSWR<TradeListResponse>(
    `${process.env.NEXT_PUBLIC_API_URL}/api/trades/?limit=100`,
    fetcher,
    { refreshInterval: 10000 },
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">거래 내역</h1>
        <p className="text-sm text-slate-400 mt-1">자동매매 거래 기록</p>
      </div>

      <TradeHistoryTable trades={data?.trades || []} isLoading={isLoading} />
    </div>
  )
}
