'use client'
/**
 * 내 지갑 상단 요약 카드 (4개)
 * - 총 자산 (USD + KRW)
 * - 현금 잔고 (USDT)
 * - 코인 가치
 * - 보유 종류 수
 */
import { Wallet, DollarSign, Bitcoin, Layers } from 'lucide-react'
import type { WalletBalance } from '@/types/wallet'
import { formatUSD, formatKRW } from '@/lib/utils'

interface WalletSummaryCardsProps {
  data: WalletBalance
}

export function WalletSummaryCards({ data }: WalletSummaryCardsProps) {
  const cards = [
    {
      label: '총 자산',
      value: formatUSD(data.total_usd),
      sub: formatKRW(data.total_krw),
      icon: Wallet,
      iconColor: 'text-blue-400',
      bgColor: 'bg-blue-500/10',
    },
    {
      label: '현금 잔고 (USDT)',
      value: formatUSD(data.cash_usd),
      sub: `${((data.cash_usd / data.total_usd) * 100).toFixed(1)}% 비중`,
      icon: DollarSign,
      iconColor: 'text-green-400',
      bgColor: 'bg-green-500/10',
    },
    {
      label: '코인 가치',
      value: formatUSD(data.coin_value_usd),
      sub: formatKRW(data.coin_value_usd * data.fx_rate),
      icon: Bitcoin,
      iconColor: 'text-yellow-400',
      bgColor: 'bg-yellow-500/10',
    },
    {
      label: '보유 종류',
      value: `${data.asset_count}종`,
      sub: `$1 = ₩${data.fx_rate.toLocaleString('ko-KR', { maximumFractionDigits: 0 })}`,
      icon: Layers,
      iconColor: 'text-purple-400',
      bgColor: 'bg-purple-500/10',
    },
  ]

  return (
    <div className="grid grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-slate-800/50 border border-slate-700 rounded-xl p-5"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-slate-400">{card.label}</span>
            <div className={`w-8 h-8 ${card.bgColor} rounded-lg flex items-center justify-center`}>
              <card.icon size={16} className={card.iconColor} />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-100">{card.value}</div>
          <div className="text-xs text-slate-500 mt-1">{card.sub}</div>
        </div>
      ))}
    </div>
  )
}
