'use client'
/**
 * 현재 보유 포지션 테이블 컴포넌트
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatUSD, formatAmount, formatPercent, getPnlColor } from '@/lib/utils'
import type { Position } from '@/types/portfolio'

interface PositionTableProps {
  positions: Record<string, Position>
}

export function PositionTable({ positions }: PositionTableProps) {
  const positionList = Object.values(positions)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>보유 포지션</span>
          <span className="text-sm font-normal text-slate-400">({positionList.length}개)</span>
          <span className="text-[10px] font-normal text-slate-500">거래소 현물 잔고 기준</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {positionList.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <p>현재 보유 포지션이 없습니다</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left pb-3 text-slate-400 font-medium">심볼</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">수량</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">진입가</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">현재가</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">미실현 손익</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">손절가</th>
                  <th className="text-right pb-3 text-slate-400 font-medium">익절가</th>
                  <th className="text-center pb-3 text-slate-400 font-medium">추적</th>
                </tr>
              </thead>
              <tbody>
                {positionList.map((position) => {
                  const pnlPct = position.entry_price > 0
                    ? ((position.current_price - position.entry_price) / position.entry_price) * 100
                    : 0

                  return (
                    <tr
                      key={position.symbol}
                      className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors"
                    >
                      <td className="py-3">
                        <span className="font-semibold text-slate-100">{position.symbol}</span>
                        <span className="ml-2 px-1.5 py-0.5 text-xs bg-green-500/20 text-green-400 rounded">
                          LONG
                        </span>
                      </td>
                      <td className="text-right py-3 text-slate-300">
                        {formatAmount(position.amount)}
                      </td>
                      <td className="text-right py-3 text-slate-300">
                        {formatUSD(position.entry_price)}
                      </td>
                      <td className="text-right py-3 text-slate-100 font-medium">
                        {formatUSD(position.current_price)}
                      </td>
                      <td className="text-right py-3">
                        <span className={`font-semibold ${getPnlColor(position.unrealized_pnl)}`}>
                          {formatUSD(position.unrealized_pnl)}
                        </span>
                        <span className={`ml-1 text-xs ${getPnlColor(pnlPct)}`}>
                          ({formatPercent(pnlPct)})
                        </span>
                      </td>
                      <td className="text-right py-3 text-red-400/80">
                        {position.stop_loss ? formatUSD(position.stop_loss) : '-'}
                      </td>
                      <td className="text-right py-3 text-green-400/80">
                        {position.take_profit ? formatUSD(position.take_profit) : '-'}
                      </td>
                      <td className="text-center py-3">
                        {position.managed_by_bot ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300">봇</span>
                        ) : (
                          <span className="text-slate-600 text-xs">-</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
