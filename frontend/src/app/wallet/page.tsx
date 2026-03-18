'use client'
/**
 * 내 지갑 페이지
 * Binance 계좌 잔액을 조회하고 코인별 자산을 표시
 * SWR 30초 자동 갱신 + 수동 새로고침 버튼
 */
import { useState } from 'react'
import useSWR from 'swr'
import { RefreshCw, Wallet, AlertTriangle } from 'lucide-react'
import { walletApi } from '@/services/api'
import { WalletSummaryCards } from '@/components/wallet/WalletSummaryCards'
import { AssetTable } from '@/components/wallet/AssetTable'
import { formatDateTime } from '@/lib/utils'

export default function WalletPage() {
  const [isRefreshing, setIsRefreshing] = useState(false)

  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWR('wallet-balance', () => walletApi.getBalance(), {
    refreshInterval: 30000,
    revalidateOnFocus: false,
  })

  const handleRefresh = async () => {
    setIsRefreshing(true)
    await mutate()
    setIsRefreshing(false)
  }

  return (
    <div className="flex-1 overflow-auto bg-slate-950 p-8">
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-slate-100">내 지갑</h1>
            {data && (
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
                  data.mode === 'paper'
                    ? 'text-purple-400 bg-purple-500/10 border-purple-500/30'
                    : 'text-green-400 bg-green-500/10 border-green-500/30'
                }`}
              >
                {data.mode === 'paper' ? '📄 PAPER' : '🟢 LIVE'}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-400">
            Binance 계좌 잔액 현황
            {data && (
              <span className="ml-2 text-slate-600">
                마지막 업데이트: {formatDateTime(data.updated_at)} (한국시간)
              </span>
            )}
          </p>
        </div>

        <button
          onClick={handleRefresh}
          disabled={isRefreshing || isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-300 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw
            size={14}
            className={isRefreshing || isLoading ? 'animate-spin' : ''}
          />
          새로고침
        </button>
      </div>

      {/* 에러 상태 */}
      {error && (
        <div className="flex items-center gap-3 bg-red-900/20 border border-red-700/50 rounded-xl p-4 mb-6">
          <AlertTriangle size={18} className="text-red-400 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-400">지갑 데이터 조회 실패</p>
            <p className="text-xs text-red-500 mt-0.5">
              {error?.message ?? '백엔드 서버 연결을 확인해주세요.'}
            </p>
          </div>
        </div>
      )}

      {/* 로딩 스켈레톤 */}
      {isLoading && !data && (
        <div className="space-y-4 animate-pulse">
          <div className="grid grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 h-28" />
            ))}
          </div>
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl h-64" />
        </div>
      )}

      {/* 데이터 정상 */}
      {data && (
        <div className="space-y-6">
          {/* 요약 카드 */}
          <WalletSummaryCards data={data} />

          {/* 자산 테이블 */}
          <AssetTable assets={data.assets} totalUsd={data.total_usd} />

          {/* 안내 문구 */}
          <p className="text-xs text-slate-600 text-right">
            💡 $0.0001 USD 미만 소액 자산은 기본적으로 표시되지 않을 수 있습니다.
            30초마다 자동 갱신됩니다.
          </p>
        </div>
      )}

      {/* 데이터 없음 (에러 아님) */}
      {!isLoading && !error && !data && (
        <div className="flex flex-col items-center justify-center py-32 text-slate-500">
          <Wallet size={48} className="mb-4 opacity-30" />
          <p className="text-sm">지갑 데이터를 불러올 수 없습니다.</p>
          <button
            onClick={handleRefresh}
            className="mt-4 text-xs text-blue-400 hover:underline"
          >
            다시 시도
          </button>
        </div>
      )}
    </div>
  )
}
