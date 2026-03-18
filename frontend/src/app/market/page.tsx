'use client'
/**
 * 시황 분석 페이지 (고도화)
 * 업비트 스타일 3패널: 헤더 시세 + 캔들차트(MA/BB) + 오른쪽 워치리스트/지표
 */
import { useState, useEffect, useCallback } from 'react'
import dynamic from 'next/dynamic'
import useSWR from 'swr'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  AlertTriangle,
  ChevronDown,
} from 'lucide-react'
import { fetcher, marketApi } from '@/services/api'
import { formatUSD, formatKRW, nowKST } from '@/lib/utils'
import type { WatchlistItem, Candle, TickerInfo, FxRateResponse } from '@/types/market'
import { WATCHLIST_SYMBOLS } from '@/constants/symbols'

// SSR 비활성화 (lightweight-charts는 브라우저 전용)
const CandleChart = dynamic(() => import('@/components/market/CandleChart'), { ssr: false })

// ── 타입 ─────────────────────────────────────────────
type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1d'
const TIMEFRAMES: { label: string; value: Timeframe }[] = [
  { label: '1분', value: '1m' },
  { label: '5분', value: '5m' },
  { label: '15분', value: '15m' },
  { label: '1시간', value: '1h' },
  { label: '4시간', value: '4h' },
  { label: '일', value: '1d' },
]

const SYMBOLS = [...WATCHLIST_SYMBOLS]
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002'

// ── 서브 컴포넌트: 가격 변동률 뱃지 ───────────────────
function ChangeBadge({ value, className = '' }: { value: number; className?: string }) {
  const isUp = value >= 0
  return (
    <span
      className={`inline-flex items-center gap-0.5 font-medium ${
        isUp ? 'text-blue-400' : 'text-red-400'
      } ${className}`}
    >
      {isUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
      {isUp ? '+' : ''}{value.toFixed(2)}%
    </span>
  )
}

// ── 서브 컴포넌트: 방향성 뱃지 ───────────────────────
function DirectionBadge({ direction }: { direction: string }) {
  const styles: Record<string, string> = {
    BULLISH: 'bg-blue-500/20 text-blue-400 border border-blue-500/40',
    BEARISH: 'bg-red-500/20 text-red-400 border border-red-500/40',
    NEUTRAL: 'bg-slate-600/40 text-slate-400 border border-slate-600',
  }
  const labels: Record<string, string> = {
    BULLISH: '🟢 상승',
    BEARISH: '🔴 하락',
    NEUTRAL: '⚪ 중립',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[direction] || styles.NEUTRAL}`}>
      {labels[direction] || direction}
    </span>
  )
}

// ── 서브 컴포넌트: RSI 상태 ────────────────────────
function rsiLabel(rsi?: number) {
  if (rsi === undefined) return { text: '-', color: 'text-slate-400' }
  if (rsi >= 70) return { text: '과매수', color: 'text-red-400' }
  if (rsi <= 30) return { text: '과매도', color: 'text-blue-400' }
  return { text: '중립', color: 'text-slate-400' }
}

// ── 서브 컴포넌트: 워치리스트 행 ──────────────────────
function WatchRow({
  coin,
  active,
  onClick,
  krwRate,
}: {
  coin: WatchlistItem
  active: boolean
  onClick: () => void
  krwRate: number
}) {
  const isUp = coin.change_24h >= 0
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg transition-colors text-sm ${
        active
          ? 'bg-blue-500/20 border border-blue-500/30'
          : 'hover:bg-slate-700/50'
      }`}
    >
      <span className="font-medium text-slate-200">{coin.symbol.replace('/USDT', '')}</span>
      <div className="text-right">
        <p className="text-slate-100 font-mono text-xs">
          {coin.price === 0 ? '-' : formatUSD(coin.price)}
        </p>
        {krwRate > 0 && coin.price > 0 && (
          <p className="text-slate-500 font-mono text-[10px]">
            {formatKRW(coin.price * krwRate)}
          </p>
        )}
        <p className={`text-xs ${isUp ? 'text-blue-400' : 'text-red-400'}`}>
          {isUp ? '+' : ''}{coin.change_24h.toFixed(2)}%
        </p>
      </div>
    </button>
  )
}

// ── 메인 페이지 ───────────────────────────────────────
export default function MarketPage() {
  const [symbol, setSymbol] = useState('BTC/USDT')
  const [timeframe, setTimeframe] = useState<Timeframe>('1h')
  const [showMA, setShowMA] = useState(true)
  const [showBB, setShowBB] = useState(true)
  const [kst, setKst] = useState('')
  const [candles, setCandles] = useState<Candle[]>([])
  const [candleLoading, setCandleLoading] = useState(false)
  const [showSymbolMenu, setShowSymbolMenu] = useState(false)

  // ── KST 시계 ───────────────────────────────────────
  useEffect(() => {
    setKst(nowKST())
    const id = setInterval(() => setKst(nowKST()), 1000)
    return () => clearInterval(id)
  }, [])

  // ── USD/KRW 환율 (5분 캐시) ────────────────────────
  const { data: fxData } = useSWR<FxRateResponse>(
    `${API}/api/market/fx`,
    fetcher,
    { refreshInterval: 5 * 60 * 1000 }
  )
  const krwRate = fxData?.usd_krw ?? 0

  // ── 워치리스트 ──────────────────────────────────────
  const { data: watchlist, mutate: mutateWatchlist } = useSWR(
    `${API}/api/market/watchlist`,
    fetcher,
    { refreshInterval: 30_000 }
  )

  // ── 선택된 심볼 시세 ────────────────────────────────
  const { data: ticker, mutate: mutateTicker } = useSWR<TickerInfo>(
    `${API}/api/market/ticker/${encodeURIComponent(symbol)}`,
    fetcher,
    { refreshInterval: 10_000 }
  )

  // ── 캔들 데이터 ────────────────────────────────────
  const loadCandles = useCallback(async () => {
    setCandleLoading(true)
    try {
      const res = await marketApi.getCandles(symbol, timeframe, 300)
      setCandles(res.candles)
    } catch {
      setCandles([])
    } finally {
      setCandleLoading(false)
    }
  }, [symbol, timeframe])

  useEffect(() => {
    loadCandles()
    const id = setInterval(loadCandles, 30_000)
    return () => clearInterval(id)
  }, [loadCandles])

  const handleRefresh = () => {
    loadCandles()
    mutateTicker()
    mutateWatchlist()
  }

  const coins: WatchlistItem[] = watchlist?.coins || SYMBOLS.map(s => ({ symbol: s, price: 0, change_24h: 0 }))
  const ind = ticker?.indicators || {}
  const rsi = ind.rsi
  const { text: rsiText, color: rsiColor } = rsiLabel(rsi)

  return (
    <div className="flex flex-col h-full min-h-0 gap-0">
      {/* ── 상단 헤더 시세 바 ─────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-800/60 border-b border-slate-700/50">
        {/* 심볼 선택 */}
        <div className="relative">
          <button
            onClick={() => setShowSymbolMenu(v => !v)}
            className="flex items-center gap-2 text-slate-100 font-bold text-lg hover:text-white transition-colors"
          >
            {symbol}
            <ChevronDown size={16} className="text-slate-400" />
          </button>
          {showSymbolMenu && (
            <div className="absolute top-full left-0 mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-2xl z-50 min-w-[160px]">
              {SYMBOLS.map(s => (
                <button
                  key={s}
                  onClick={() => { setSymbol(s); setShowSymbolMenu(false) }}
                  className={`w-full text-left px-4 py-2.5 text-sm transition-colors first:rounded-t-lg last:rounded-b-lg ${
                    s === symbol ? 'bg-blue-500/20 text-blue-400' : 'text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 현재가 + 변동 */}
        <div className="flex items-center gap-6">
          {ticker ? (
            <>
              <div className="text-center">
                <p className={`text-2xl font-bold font-mono ${ticker.change_24h >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
                  {formatUSD(ticker.price)}
                </p>
                {krwRate > 0 && (
                  <p className="text-xs text-slate-400 font-mono mt-0.5">
                    {formatKRW(ticker.price * krwRate)}
                  </p>
                )}
                <ChangeBadge value={ticker.change_24h} />
              </div>
              <div className="hidden md:grid grid-cols-3 gap-x-6 gap-y-0.5 text-xs">
                <span className="text-slate-500">고가 (24h)</span>
                <span className="text-slate-500">저가 (24h)</span>
                <span className="text-slate-500">거래량 (24h)</span>
                <span className="text-blue-400 font-mono">{formatUSD(ticker.high_24h)}</span>
                <span className="text-red-400 font-mono">{formatUSD(ticker.low_24h)}</span>
                <span className="text-slate-300 font-mono">{formatUSD(ticker.volume_24h, 0)}</span>
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2 text-slate-500 text-sm">
              <AlertTriangle size={16} />
              <span>시세 불러오는 중…</span>
            </div>
          )}
        </div>

        {/* 시계 + 새로고침 */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 font-mono">{kst} KST</span>
          <button
            onClick={handleRefresh}
            className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
            title="새로고침"
          >
            <RefreshCw size={15} className={candleLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* ── 메인 2분할: 차트 | 사이드 ──────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* ── 왼쪽: 차트 영역 ──────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 bg-slate-900">
          {/* 타임프레임 + 지표 토글 */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700/50 bg-slate-800/40">
            <div className="flex items-center gap-1">
              {TIMEFRAMES.map(tf => (
                <button
                  key={tf.value}
                  onClick={() => setTimeframe(tf.value)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    timeframe === tf.value
                      ? 'bg-blue-500 text-white'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowMA(v => !v)}
                className={`px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
                  showMA
                    ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400'
                    : 'border-slate-600 text-slate-500 hover:border-slate-500'
                }`}
              >
                MA
              </button>
              <button
                onClick={() => setShowBB(v => !v)}
                className={`px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
                  showBB
                    ? 'bg-slate-500/30 border-slate-500 text-slate-300'
                    : 'border-slate-600 text-slate-500 hover:border-slate-500'
                }`}
              >
                BB
              </button>
            </div>
          </div>

          {/* 지표 범례 */}
          {(showMA || showBB) && (
            <div className="flex items-center gap-4 px-3 py-1.5 bg-slate-900/80 text-xs">
              {showMA && (
                <>
                  <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-yellow-400 inline-block" />MA20</span>
                  <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-orange-400 inline-block" />MA50</span>
                  <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-purple-400 inline-block" />MA200</span>
                </>
              )}
              {showBB && (
                <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-slate-400 inline-block border-t border-dashed border-slate-400" />볼린저밴드</span>
              )}
            </div>
          )}

          {/* 차트 */}
          <div className="flex-1 min-h-0 relative">
            {candleLoading && candles.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500">
                <RefreshCw size={28} className="animate-spin mb-3" />
                <p className="text-sm">캔들 데이터 로딩 중…</p>
              </div>
            ) : candles.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500">
                <AlertTriangle size={28} className="mb-3" />
                <p className="text-sm">캔들 데이터를 불러올 수 없습니다.</p>
                <p className="text-xs mt-1 text-slate-600">백엔드 연결 상태를 확인해주세요.</p>
              </div>
            ) : (
              <CandleChart
                candles={candles}
                showMA={showMA}
                showBB={showBB}
                height={580}
              />
            )}
          </div>
        </div>

        {/* ── 오른쪽: 워치리스트 + 지표 ────────────────── */}
        <div className="w-64 flex-shrink-0 flex flex-col border-l border-slate-700/50 bg-slate-800/30 overflow-y-auto">
          {/* 워치리스트 */}
          <div className="p-3 border-b border-slate-700/50">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">워치리스트</p>
              {krwRate > 0 && (
                <span className="text-[10px] text-slate-600 font-mono">
                  $1 = {formatKRW(krwRate)}
                </span>
              )}
            </div>
            <div className="space-y-0.5">
              {coins.map(coin => (
                <WatchRow
                  key={coin.symbol}
                  coin={coin}
                  active={coin.symbol === symbol}
                  onClick={() => setSymbol(coin.symbol)}
                  krwRate={krwRate}
                />
              ))}
            </div>
          </div>

          {/* 기술적 지표 */}
          <div className="p-3 border-b border-slate-700/50">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">기술 지표</p>
            {ticker ? (
              <div className="space-y-3">
                {/* 방향성 */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">방향성</span>
                  <DirectionBadge direction={ticker.direction} />
                </div>

                {/* 신뢰도 */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-slate-400">신뢰도</span>
                    <span className="text-xs text-slate-300">{(ticker.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        ticker.direction === 'BULLISH' ? 'bg-blue-500' :
                        ticker.direction === 'BEARISH' ? 'bg-red-500' : 'bg-slate-500'
                      }`}
                      style={{ width: `${ticker.confidence * 100}%` }}
                    />
                  </div>
                </div>

                {/* RSI */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">RSI (14)</span>
                  <span className={`text-xs font-mono font-medium ${rsiColor}`}>
                    {rsi?.toFixed(1) || '-'} <span className="font-normal">{rsiText}</span>
                  </span>
                </div>
                {rsi !== undefined && (
                  <div className="relative h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div className="absolute left-[30%] right-[30%] h-full bg-slate-600 opacity-50" />
                    <div
                      className={`absolute top-0 h-full w-1.5 -ml-0.5 rounded-full ${rsiColor.replace('text-', 'bg-')}`}
                      style={{ left: `${Math.min(Math.max(rsi, 0), 100)}%` }}
                    />
                  </div>
                )}

                {/* MACD */}
                {ind.macd_diff !== undefined && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">MACD</span>
                    <span className={`text-xs font-mono ${ind.macd_diff >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
                      {ind.macd_diff >= 0 ? '▲ 양' : '▼ 음'} ({ind.macd_diff.toFixed(2)})
                    </span>
                  </div>
                )}

                {/* 볼린저밴드 */}
                {ind.bb_upper !== undefined && ind.bb_lower !== undefined && ind.bb_middle !== undefined && ticker.price && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">볼린저</span>
                    <span className="text-xs text-slate-300">
                      {ticker.price >= ind.bb_upper ? '상단 돌파' :
                       ticker.price <= ind.bb_lower ? '하단 돌파' : '밴드 내'}
                    </span>
                  </div>
                )}

                {/* MA 크로스 */}
                {ind.ma20 !== undefined && ind.ma50 !== undefined && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">MA 크로스</span>
                    <span className={`text-xs ${ind.ma20 > ind.ma50 ? 'text-blue-400' : 'text-red-400'}`}>
                      {ind.ma20 > ind.ma50 ? '골든크로스' : '데드크로스'}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-600">데이터 로딩 중…</p>
            )}
          </div>

          {/* OpenClaw 신호 */}
          <div className="p-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">OpenClaw 신호</p>
            {ticker ? (
              <div className={`rounded-lg p-3 border ${
                ticker.direction === 'BULLISH'
                  ? 'bg-blue-500/10 border-blue-500/30'
                  : ticker.direction === 'BEARISH'
                    ? 'bg-red-500/10 border-red-500/30'
                    : 'bg-slate-700/30 border-slate-600/30'
              }`}>
                <DirectionBadge direction={ticker.direction} />
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                  {ticker.direction === 'BULLISH'
                    ? '기술 지표가 매수를 지지합니다. 에이전트가 진입 기회를 탐색 중입니다.'
                    : ticker.direction === 'BEARISH'
                      ? '기술 지표가 매도 압력을 나타냅니다. 에이전트가 리스크를 관리합니다.'
                      : '명확한 방향성이 없습니다. 에이전트가 관망 중입니다.'}
                </p>
              </div>
            ) : (
              <p className="text-xs text-slate-600">대기 중…</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
