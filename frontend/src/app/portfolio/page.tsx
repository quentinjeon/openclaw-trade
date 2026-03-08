'use client'
/**
 * 포트폴리오 페이지
 * 상세 포트폴리오 현황 및 성과 지표
 */
import useSWR from 'swr'
import { PortfolioSummary } from '@/components/dashboard/PortfolioSummary'
import { PositionTable } from '@/components/dashboard/PositionTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fetcher, tradeApi } from '@/services/api'
import { formatUSD, formatPercent, getPnlColor } from '@/lib/utils'
import type { Portfolio } from '@/types/portfolio'

export default function PortfolioPage() {
  const { data: portfolio, isLoading } = useSWR<Portfolio>(
    `${process.env.NEXT_PUBLIC_API_URL}/api/portfolio/`,
    fetcher,
    { refreshInterval: 5000 },
  )

  const handleCloseAll = async () => {
    if (!confirm('모든 포지션을 청산하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return
    try {
      await tradeApi.closeAllPositions()
      alert('전체 포지션 청산 완료')
    } catch {
      alert('청산 중 오류가 발생했습니다')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">포트폴리오</h1>
          <p className="text-sm text-slate-400 mt-1">실시간 포트폴리오 현황</p>
        </div>

        <button
          onClick={handleCloseAll}
          className="px-4 py-2 bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg text-sm font-medium hover:bg-red-500/30 transition-colors"
        >
          전체 청산
        </button>
      </div>

      <PortfolioSummary portfolio={portfolio ?? null} isLoading={isLoading} />

      {/* 성과 통계 */}
      {portfolio && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <p className="text-xs text-slate-400">현금 잔고</p>
              <p className="text-lg font-bold text-slate-100 mt-1">
                {formatUSD(portfolio.cash_usd)}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs text-slate-400">포지션 가치</p>
              <p className="text-lg font-bold text-slate-100 mt-1">
                {formatUSD(portfolio.total_value_usd - portfolio.cash_usd)}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs text-slate-400">총 손익</p>
              <p className={`text-lg font-bold mt-1 ${getPnlColor(portfolio.pnl_total)}`}>
                {portfolio.pnl_total >= 0 ? '+' : ''}{formatUSD(portfolio.pnl_total)}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs text-slate-400">총 수익률</p>
              <p className={`text-lg font-bold mt-1 ${getPnlColor(portfolio.total_return_pct)}`}>
                {formatPercent(portfolio.total_return_pct)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <PositionTable positions={portfolio?.positions ?? {}} />
    </div>
  )
}
