'use client'
/**
 * 거래 내역 테이블 컴포넌트
 */
import { ArrowUpRight, ArrowDownRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatUSD, formatAmount, formatDateTime, getPnlColor } from '@/lib/utils'
import type { Trade } from '@/types/trade'

interface TradeHistoryTableProps {
  trades: Trade[]
  isLoading?: boolean
}

export function TradeHistoryTable({ trades, isLoading }: TradeHistoryTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="animate-pulse space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-10 bg-slate-700 rounded" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>거래 내역</CardTitle>
      </CardHeader>
      <CardContent>
        {trades.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <p>거래 내역이 없습니다</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left pb-3 text-slate-400 font-medium">시간</th>
                  <th className="text-left pb-3 text-slate-400 font-medium">심볼</th>
                  <th className="text-left pb-3 text-slate-400 font-medium">구분</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">수량</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">가격</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">비용</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">손익</th>
                  <th className="text-left pb-3 text-slate-400 font-medium">전략</th>
                  <th className="text-center pb-3 text-slate-400 font-medium">구분</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => (
                  <tr
                    key={trade.id}
                    className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors"
                  >
                    <td className="py-3 text-slate-500 text-xs">
                      {formatDateTime(trade.created_at)}
                    </td>
                    <td className="py-3 font-semibold text-slate-100">{trade.symbol}</td>
                    <td className="py-3">
                      <div className="flex items-center gap-1">
                        {trade.side === 'buy' ? (
                          <>
                            <ArrowUpRight size={14} className="text-green-400" />
                            <span className="text-green-400 font-medium">매수</span>
                          </>
                        ) : (
                          <>
                            <ArrowDownRight size={14} className="text-red-400" />
                            <span className="text-red-400 font-medium">매도</span>
                          </>
                        )}
                      </div>
                    </td>
                    <td className="text-right py-3 text-slate-300">
                      {formatAmount(trade.amount)}
                    </td>
                    <td className="text-right py-3 text-slate-300">
                      {formatUSD(trade.price)}
                    </td>
                    <td className="text-right py-3 text-slate-300">
                      {formatUSD(trade.cost)}
                    </td>
                    <td className="text-right py-3">
                      {trade.pnl !== undefined && trade.pnl !== null ? (
                        <span className={`font-semibold ${getPnlColor(trade.pnl)}`}>
                          {trade.pnl >= 0 ? '+' : ''}{formatUSD(trade.pnl)}
                        </span>
                      ) : (
                        <span className="text-slate-600">-</span>
                      )}
                    </td>
                    <td className="py-3">
                      <span className="text-xs px-1.5 py-0.5 bg-slate-700 rounded text-slate-400">
                        {trade.strategy || '-'}
                      </span>
                    </td>
                    <td className="text-center py-3">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${trade.is_paper ? 'bg-purple-500/20 text-purple-400' : 'bg-green-500/20 text-green-400'}`}>
                        {trade.is_paper ? 'PAPER' : 'LIVE'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
