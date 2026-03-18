'use client'
/**
 * 포트폴리오 요약 카드 컴포넌트
 * 총 자산, 일일 손익, 승률 등 핵심 지표를 표시
 */
import { TrendingUp, TrendingDown, Wallet, Target, BarChart3, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { formatUSD, formatPercent, getPnlColor } from '@/lib/utils'
import type { Portfolio } from '@/types/portfolio'

interface MetricCardProps {
  title: string
  value: string
  subtitle?: string
  icon: React.ReactNode
  valueColor?: string
}

function MetricCard({ title, value, subtitle, icon, valueColor }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-400">{title}</span>
          <div className="text-slate-500">{icon}</div>
        </div>
        <div className={`text-2xl font-bold ${valueColor || 'text-slate-100'}`}>{value}</div>
        {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
      </CardContent>
    </Card>
  )
}

interface PortfolioSummaryProps {
  portfolio: Portfolio | null
  isLoading?: boolean
}

export function PortfolioSummary({ portfolio, isLoading }: PortfolioSummaryProps) {
  if (isLoading || !portfolio) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="p-6">
              <div className="animate-pulse space-y-3">
                <div className="h-4 bg-slate-700 rounded w-1/2" />
                <div className="h-8 bg-slate-700 rounded w-3/4" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const metrics = [
    {
      title: '총 자산',
      value: formatUSD(portfolio.total_value_usd),
      subtitle: portfolio.live_trading
        ? `현금 ${formatUSD(portfolio.cash_usd)} · 거래소 동기화`
        : `초기 ${formatUSD(portfolio.initial_balance)}`,
      icon: <Wallet size={18} />,
      valueColor: 'text-slate-100',
    },
    {
      title: '총 수익률',
      value: formatPercent(portfolio.total_return_pct),
      subtitle: `${getPnlLabel(portfolio.pnl_total)} ${formatUSD(Math.abs(portfolio.pnl_total))}`,
      icon:
        portfolio.total_return_pct >= 0 ? <TrendingUp size={18} className="text-green-400" /> : <TrendingDown size={18} className="text-red-400" />,
      valueColor: getPnlColor(portfolio.total_return_pct),
    },
    {
      title: '오늘 손익',
      value: formatUSD(portfolio.pnl_today),
      subtitle: `총 거래: ${portfolio.total_trades}건`,
      icon: <BarChart3 size={18} />,
      valueColor: getPnlColor(portfolio.pnl_today),
    },
    {
      title: '승률',
      value: `${portfolio.win_rate.toFixed(1)}%`,
      subtitle: `${portfolio.winning_trades}승 / ${portfolio.losing_trades}패`,
      icon: <Target size={18} className="text-blue-400" />,
      valueColor: portfolio.win_rate >= 50 ? 'text-green-400' : 'text-red-400',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((metric) => (
        <MetricCard key={metric.title} {...metric} />
      ))}
    </div>
  )
}

function getPnlLabel(pnl: number): string {
  return pnl >= 0 ? '수익' : '손실'
}
