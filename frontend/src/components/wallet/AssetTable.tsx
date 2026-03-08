'use client'
/**
 * 코인별 자산 테이블
 * - 수량, 현재가, 평가금액 (USD + KRW), 비중 프로그레스 바, 24h 변동률
 */
import { useState } from 'react'
import { EyeOff, Eye } from 'lucide-react'
import type { WalletAsset } from '@/types/wallet'
import { formatUSD, formatKRW, formatAmount, formatPercent, getPnlColor } from '@/lib/utils'

interface AssetTableProps {
  assets: WalletAsset[]
  totalUsd: number
}

// 코인별 프로그레스 바 색상
const COIN_COLORS: Record<string, string> = {
  BTC: 'bg-yellow-500',
  ETH: 'bg-blue-400',
  BNB: 'bg-yellow-400',
  SOL: 'bg-purple-400',
  XRP: 'bg-blue-300',
  USDT: 'bg-green-500',
  USDC: 'bg-blue-500',
  BUSD: 'bg-yellow-300',
}

function getCoinColor(currency: string): string {
  return COIN_COLORS[currency] ?? 'bg-slate-500'
}

// 소액 기준 (USD)
const DUST_THRESHOLD = 0.01

export function AssetTable({ assets, totalUsd }: AssetTableProps) {
  const [hideDust, setHideDust] = useState(false)

  const displayed = hideDust
    ? assets.filter((a) => a.usd_value >= DUST_THRESHOLD)
    : assets

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <h2 className="text-sm font-semibold text-slate-200">
          보유 자산 목록{' '}
          <span className="text-slate-500 font-normal">({displayed.length}개)</span>
        </h2>
        <button
          onClick={() => setHideDust((prev) => !prev)}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors px-3 py-1.5 rounded-lg bg-slate-700/50 hover:bg-slate-700"
        >
          {hideDust ? <Eye size={13} /> : <EyeOff size={13} />}
          {hideDust ? '소액 표시' : '소액 숨기기'}
        </button>
      </div>

      {/* 테이블 */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-500 text-xs border-b border-slate-700/50">
              <th className="text-left px-6 py-3 font-medium">코인</th>
              <th className="text-right px-4 py-3 font-medium">보유 수량</th>
              <th className="text-right px-4 py-3 font-medium">현재가</th>
              <th className="text-right px-4 py-3 font-medium">평가금액</th>
              <th className="text-right px-4 py-3 font-medium">KRW 환산</th>
              <th className="text-right px-4 py-3 font-medium">비중</th>
              <th className="text-right px-6 py-3 font-medium">24h</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/30">
            {displayed.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-12 text-slate-500">
                  보유 자산이 없습니다
                </td>
              </tr>
            ) : (
              displayed.map((asset) => (
                <tr
                  key={asset.currency}
                  className="hover:bg-slate-700/20 transition-colors"
                >
                  {/* 코인명 */}
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-8 h-8 ${getCoinColor(asset.currency)} rounded-full flex items-center justify-center text-xs font-bold text-white`}
                      >
                        {asset.currency.slice(0, 2)}
                      </div>
                      <span className="font-medium text-slate-100">{asset.currency}</span>
                    </div>
                  </td>

                  {/* 보유 수량 */}
                  <td className="px-4 py-4 text-right text-slate-300 tabular-nums">
                    {formatAmount(asset.amount)}
                  </td>

                  {/* 현재가 */}
                  <td className="px-4 py-4 text-right text-slate-300 tabular-nums">
                    {asset.currency === 'USDT' ||
                    asset.currency === 'USDC' ||
                    asset.currency === 'BUSD'
                      ? '$1.00'
                      : formatUSD(asset.current_price_usd, asset.current_price_usd >= 1 ? 2 : 6)}
                  </td>

                  {/* 평가금액 USD */}
                  <td className="px-4 py-4 text-right tabular-nums">
                    <div className="text-slate-100 font-medium">
                      {formatUSD(asset.usd_value)}
                    </div>
                  </td>

                  {/* KRW 환산 */}
                  <td className="px-4 py-4 text-right text-slate-400 tabular-nums text-xs">
                    {formatKRW(asset.krw_value)}
                  </td>

                  {/* 비중 */}
                  <td className="px-4 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 bg-slate-700 rounded-full h-1.5">
                        <div
                          className={`${getCoinColor(asset.currency)} h-1.5 rounded-full transition-all`}
                          style={{ width: `${Math.min(asset.pct_of_total, 100)}%` }}
                        />
                      </div>
                      <span className="text-slate-300 tabular-nums text-xs w-12 text-right">
                        {asset.pct_of_total.toFixed(1)}%
                      </span>
                    </div>
                  </td>

                  {/* 24h 변동률 */}
                  <td className={`px-6 py-4 text-right tabular-nums font-medium ${getPnlColor(asset.change_24h_pct)}`}>
                    {asset.currency === 'USDT' ||
                    asset.currency === 'USDC' ||
                    asset.currency === 'BUSD'
                      ? '—'
                      : formatPercent(asset.change_24h_pct)}
                  </td>
                </tr>
              ))
            )}
          </tbody>

          {/* 합계 행 */}
          {displayed.length > 0 && (
            <tfoot className="border-t border-slate-700">
              <tr className="bg-slate-800/30">
                <td className="px-6 py-3 text-slate-400 text-xs font-medium">합계</td>
                <td colSpan={2} />
                <td className="px-4 py-3 text-right text-slate-100 font-semibold tabular-nums">
                  {formatUSD(totalUsd)}
                </td>
                <td className="px-4 py-3 text-right text-slate-400 text-xs tabular-nums">
                  {formatKRW(displayed.reduce((acc, a) => acc + a.krw_value, 0))}
                </td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}
