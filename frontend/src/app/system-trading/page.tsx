'use client'
/**
 * 시스템 트레이딩 페이지
 *
 * 레이아웃: 좌(차트 + 백테스트 결과) | 우(조건식 편집 패널)
 * - TradingView 스타일 캔들 차트 + Buy/Sell 마커
 * - 조건식 CRUD (매수/매도 조건 시각 편집)
 * - AI Text-to-Rule (자연어 → 조건 변환)
 * - 백테스트 실행 → 통계 + 차트 마커 표시
 * - 전략 템플릿 5종 제공
 */
import { useState, useEffect, useCallback } from 'react'
import dynamic from 'next/dynamic'
import useSWR from 'swr'
import {
  Play, Save, Plus, ChevronDown, ChevronUp, RefreshCw,
  Trash2, FileText, BarChart2, Settings2, Zap, AlertCircle,
  TrendingUp, CheckCircle, XCircle, Loader2,
} from 'lucide-react'
import { systemTradingApi, fetcher } from '@/services/api'
import type {
  SystemCondition,
  ConditionGroup,
  BacktestResult,
  StrategyTemplate,
} from '@/types/system_trading'
import { SYMBOL_OPTIONS, TIMEFRAME_OPTIONS } from '@/types/system_trading'
import type { ChartMarker } from '@/components/market/CandleChart'
import { ConditionBuilder } from '@/components/system-trading/ConditionBuilder'
import { BacktestResultPanel } from '@/components/system-trading/BacktestResultPanel'

const CandleChart = dynamic(() => import('@/components/market/CandleChart'), { ssr: false })

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002'

// 기본 빈 조건 그룹
const EMPTY_BUY_GROUP: ConditionGroup = { logic: 'AND', conditions: [] }
const EMPTY_SELL_GROUP: ConditionGroup = { logic: 'OR', conditions: [] }

// 조건식 요약 레이블
function condSummary(group?: ConditionGroup): string {
  if (!group || group.conditions.length === 0) return '조건 없음'
  return group.conditions.map(c => {
    const op = c.operator === 'crosses_above' ? '↑' : c.operator === 'crosses_below' ? '↓' : c.operator
    const b = c.type_b === 'value' ? String(c.value_b) : (c.indicator_b || '')
    return `${c.indicator_a} ${op} ${b}`
  }).join(` ${group.logic} `)
}

export default function SystemTradingPage() {
  // ── 심볼/타임프레임 ─────────────────────────────────
  const [symbol, setSymbol] = useState('BTC/USDT')
  const [timeframe, setTimeframe] = useState('1h')

  // ── 활성 조건식 편집 상태 ───────────────────────────
  const [condName, setCondName] = useState('새 조건식')
  const [buyGroup, setBuyGroup] = useState<ConditionGroup>(EMPTY_BUY_GROUP)
  const [sellGroup, setSellGroup] = useState<ConditionGroup>(EMPTY_SELL_GROUP)
  const [editingId, setEditingId] = useState<number | null>(null)  // null = 신규

  // ── UI 상태 ────────────────────────────────────────
  const [saving, setSaving] = useState(false)
  const [backtesting, setBacktesting] = useState(false)
  const [checkingNow, setCheckingNow] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const [showList, setShowList] = useState(true)
  const [checkResult, setCheckResult] = useState<{
    triggered: boolean; side: string; current_values: Record<string, number>
  } | null>(null)

  // ── 백테스트 결과 ───────────────────────────────────
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null)
  const [markers, setMarkers] = useState<ChartMarker[]>([])

  // ── 캔들 데이터 ─────────────────────────────────────
  const [candles, setCandles] = useState<{ time: number; open: number; high: number; low: number; close: number; volume: number }[]>([])
  const [candleLoading, setCandleLoading] = useState(false)

  // ── 조건식 목록 (SWR) ──────────────────────────────
  const { data: conditions, mutate: refetchConditions } = useSWR<SystemCondition[]>(
    `${API}/api/system/conditions`,
    fetcher,
    { refreshInterval: 0 }
  )

  // ── 전략 템플릿 (SWR) ──────────────────────────────
  const { data: templateData } = useSWR<{ templates: StrategyTemplate[] }>(
    `${API}/api/system/templates`,
    fetcher,
    { revalidateOnFocus: false }
  )
  const templates = templateData?.templates || []

  // ── 캔들 로딩 ──────────────────────────────────────
  const loadCandles = useCallback(async () => {
    setCandleLoading(true)
    try {
      const res = await fetch(`${API}/api/market/candles/${encodeURIComponent(symbol)}?timeframe=${timeframe}&limit=300`)
      if (!res.ok) throw new Error('캔들 로딩 실패')
      const data = await res.json()
      setCandles(data.candles || [])
    } catch {
      setCandles([])
    } finally {
      setCandleLoading(false)
    }
  }, [symbol, timeframe])

  useEffect(() => {
    loadCandles()
  }, [loadCandles])

  // ── 조건식 선택 ────────────────────────────────────
  const selectCondition = (cond: SystemCondition) => {
    setEditingId(cond.id)
    setCondName(cond.name)
    setBuyGroup(cond.buy_conditions || EMPTY_BUY_GROUP)
    setSellGroup(cond.sell_conditions || EMPTY_SELL_GROUP)
    setSymbol(cond.symbol)
    setTimeframe(cond.timeframe)
    setBacktestResult(null)
    setMarkers([])
    setCheckResult(null)
  }

  const newCondition = () => {
    setEditingId(null)
    setCondName('새 조건식')
    setBuyGroup(EMPTY_BUY_GROUP)
    setSellGroup(EMPTY_SELL_GROUP)
    setBacktestResult(null)
    setMarkers([])
    setCheckResult(null)
  }

  // ── 저장 ───────────────────────────────────────────
  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        name: condName,
        symbol,
        timeframe,
        buy_conditions: buyGroup,
        sell_conditions: sellGroup,
      }
      if (editingId !== null) {
        await systemTradingApi.updateCondition(editingId, payload)
      } else {
        const created = await systemTradingApi.createCondition(payload)
        setEditingId(created.id)
      }
      await refetchConditions()
    } catch (e) {
      alert('저장 실패: ' + String(e))
    } finally {
      setSaving(false)
    }
  }

  // ── 삭제 ───────────────────────────────────────────
  const handleDelete = async (id: number) => {
    if (!confirm('이 조건식을 삭제하시겠습니까?')) return
    await systemTradingApi.deleteCondition(id)
    await refetchConditions()
    if (editingId === id) newCondition()
  }

  // ── 백테스트 ──────────────────────────────────────
  const handleBacktest = async () => {
    if (buyGroup.conditions.length === 0) {
      alert('매수 조건을 하나 이상 추가해주세요.')
      return
    }
    if (sellGroup.conditions.length === 0) {
      alert('매도 조건을 하나 이상 추가해주세요.')
      return
    }
    setBacktesting(true)
    setBacktestResult(null)
    try {
      const result = await systemTradingApi.backtest({
        buy_conditions: buyGroup,
        sell_conditions: sellGroup,
        symbol,
        timeframe,
        limit: 300,
      })
      setBacktestResult(result)

      // 마커 설정 (백테스트 신호 → 차트 마커)
      // loadCandles()를 다시 호출하면 타임스탬프 불일치가 생길 수 있으므로 제거
      const m: ChartMarker[] = result.signals.map(s => ({
        time: s.time,
        type: s.type,
        price: s.price,
      }))
      setMarkers(m)
    } catch (e) {
      alert('백테스트 실패: ' + String(e))
    } finally {
      setBacktesting(false)
    }
  }

  // ── 현재 조건 체크 ────────────────────────────────
  const handleCheckNow = async () => {
    setCheckingNow(true)
    setCheckResult(null)
    try {
      const result = await systemTradingApi.checkNow({
        buy_conditions: buyGroup,
        sell_conditions: sellGroup,
        symbol,
      })
      setCheckResult(result)
    } catch (e) {
      alert('조건 체크 실패: ' + String(e))
    } finally {
      setCheckingNow(false)
    }
  }

  // ── 템플릿 적용 ────────────────────────────────────
  const applyTemplate = (tmpl: StrategyTemplate) => {
    setCondName(tmpl.name)
    setBuyGroup(tmpl.buy_group)
    setSellGroup(tmpl.sell_group)
    setEditingId(null)
    setShowTemplates(false)
    setBacktestResult(null)
    setMarkers([])
  }

  return (
    <div className="flex h-full min-h-0 overflow-hidden">
      {/* ────────────────────────────────────────────────── */}
      {/* 왼쪽: 차트 영역                                    */}
      {/* ────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
        {/* 차트 툴바 */}
        <div className="flex items-center justify-between px-4 py-2 bg-slate-800/60 border-b border-slate-700/50 flex-shrink-0">
          <div className="flex items-center gap-2">
            {/* 심볼 */}
            <select
              value={symbol}
              onChange={e => setSymbol(e.target.value)}
              className="text-sm bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 focus:outline-none"
            >
              {SYMBOL_OPTIONS.map(s => (
                <option key={s} value={s}>{s.replace('/USDT', '')}</option>
              ))}
            </select>
            {/* 타임프레임 */}
            <div className="flex items-center gap-0.5">
              {TIMEFRAME_OPTIONS.map(tf => (
                <button
                  key={tf.value}
                  onClick={() => setTimeframe(tf.value)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                    timeframe === tf.value
                      ? 'bg-blue-500 text-white'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
            <button
              onClick={loadCandles}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <RefreshCw size={13} className={candleLoading ? 'animate-spin' : ''} />
            </button>
          </div>

          {/* 마커 범례 */}
          {markers.length > 0 && (
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-green-400">
                <span className="font-bold">▲</span> 매수 신호
              </span>
              <span className="flex items-center gap-1 text-red-400">
                <span className="font-bold">▼</span> 매도 신호
              </span>
              <span className="text-slate-500">{markers.length}건</span>
            </div>
          )}
        </div>

        {/* 차트 */}
        <div className="flex-1 min-h-0 bg-slate-900 relative overflow-hidden">
          {candleLoading && candles.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center text-slate-500">
              <Loader2 size={24} className="animate-spin mr-2" />
              <span className="text-sm">캔들 로딩 중...</span>
            </div>
          ) : candles.length > 0 ? (
            <CandleChart
              candles={candles}
              showMA={true}
              showBB={false}
              height={backtestResult ? 460 : 580}
              markers={markers}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-slate-500">
              <AlertCircle size={24} className="mr-2" />
              <span className="text-sm">데이터를 불러올 수 없습니다.</span>
            </div>
          )}
        </div>

        {/* 백테스트 결과 패널 */}
        {backtestResult && (
          <div className="flex-shrink-0 max-h-52 overflow-y-auto">
            <BacktestResultPanel
              result={backtestResult}
              symbol={symbol}
              timeframe={timeframe}
            />
          </div>
        )}
      </div>

      {/* ────────────────────────────────────────────────── */}
      {/* 오른쪽: 조건식 편집 패널                          */}
      {/* ────────────────────────────────────────────────── */}
      <div className="w-96 flex-shrink-0 flex flex-col border-l border-slate-700/50 bg-slate-800/20 overflow-y-auto">
        {/* 조건식 목록 토글 */}
        <div className="border-b border-slate-700/50">
          <button
            onClick={() => setShowList(v => !v)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-300 hover:text-white transition-colors"
          >
            <span className="flex items-center gap-2">
              <FileText size={14} className="text-blue-400" />
              내 조건식 목록 ({conditions?.length ?? 0}개)
            </span>
            {showList ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {showList && (
            <div className="px-3 pb-3 space-y-1 max-h-52 overflow-y-auto">
              {/* 새 조건식 버튼 */}
              <button
                onClick={newCondition}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-blue-400 border border-blue-500/30 hover:bg-blue-500/10 transition-colors"
              >
                <Plus size={12} /> 새 조건식 만들기
              </button>

              {conditions && conditions.length > 0 ? (
                conditions.map(cond => (
                  <div
                    key={cond.id}
                    className={`flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors border ${
                      editingId === cond.id
                        ? 'bg-blue-500/15 border-blue-500/30 text-slate-200'
                        : 'border-transparent hover:bg-slate-700/30 text-slate-400'
                    }`}
                    onClick={() => selectCondition(cond)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{cond.name}</p>
                      <p className="text-[10px] text-slate-600 truncate">{cond.symbol} • {cond.timeframe}</p>
                      {cond.backtest_win_rate !== undefined && cond.backtest_win_rate !== null && (
                        <p className="text-[10px] text-slate-600">
                          승률 {cond.backtest_win_rate}% • {cond.backtest_total_trades}건
                        </p>
                      )}
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(cond.id) }}
                      className="p-1 text-slate-600 hover:text-red-400 transition-colors flex-shrink-0"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-600 text-center py-2">저장된 조건식이 없습니다</p>
              )}
            </div>
          )}
        </div>

        {/* ── 편집 영역 ───────────────────────────────── */}
        <div className="flex-1 p-4 space-y-4">
          {/* 조건식 이름 */}
          <div>
            <label className="text-xs text-slate-500 mb-1 block">조건식 이름</label>
            <input
              value={condName}
              onChange={e => setCondName(e.target.value)}
              className="w-full text-sm bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
              placeholder="조건식 이름 입력"
            />
          </div>

          {/* 전략 템플릿 */}
          <div>
            <button
              onClick={() => setShowTemplates(v => !v)}
              className="w-full flex items-center justify-between px-3 py-2 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-600 rounded-lg text-xs text-slate-300 transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <Zap size={12} className="text-yellow-400" />
                전략 템플릿으로 시작하기
              </span>
              {showTemplates ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {showTemplates && (
              <div className="mt-2 space-y-1.5">
                {templates.map(tmpl => (
                  <button
                    key={tmpl.key}
                    onClick={() => applyTemplate(tmpl)}
                    className="w-full text-left px-3 py-2.5 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-600 hover:border-blue-500/40 rounded-lg transition-colors"
                  >
                    <p className="text-xs font-medium text-slate-200">{tmpl.name}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{tmpl.description}</p>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 매수 조건 */}
          <ConditionBuilder
            label="📈 매수 조건"
            color="green"
            group={buyGroup}
            onChange={setBuyGroup}
          />

          {/* 매도 조건 */}
          <ConditionBuilder
            label="📉 매도 조건"
            color="red"
            group={sellGroup}
            onChange={setSellGroup}
          />

          {/* 현재 조건 체크 결과 */}
          {checkResult && (
            <div className={`rounded-xl border p-3 ${
              checkResult.side === 'BUY'
                ? 'bg-green-500/10 border-green-500/30'
                : checkResult.side === 'SELL'
                  ? 'bg-red-500/10 border-red-500/30'
                  : 'bg-slate-700/30 border-slate-600'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                {checkResult.triggered
                  ? <CheckCircle size={14} className={checkResult.side === 'BUY' ? 'text-green-400' : 'text-red-400'} />
                  : <XCircle size={14} className="text-slate-400" />
                }
                <span className={`text-sm font-semibold ${
                  checkResult.side === 'BUY' ? 'text-green-400'
                  : checkResult.side === 'SELL' ? 'text-red-400'
                  : 'text-slate-400'
                }`}>
                  {checkResult.side === 'BUY' ? '🟢 매수 조건 발동!'
                  : checkResult.side === 'SELL' ? '🔴 매도 조건 발동!'
                  : '⚪ 조건 미발동'}
                </span>
              </div>
              <div className="text-[10px] text-slate-500 space-y-0.5">
                {Object.entries(checkResult.current_values).map(([k, v]) => (
                  <p key={k}>{k}: {typeof v === 'number' ? v.toFixed(4) : v}</p>
                ))}
              </div>
            </div>
          )}

          {/* 액션 버튼 */}
          <div className="space-y-2 pb-6">
            {/* 지금 체크 */}
            <button
              onClick={handleCheckNow}
              disabled={checkingNow || buyGroup.conditions.length === 0}
              className="w-full py-2 flex items-center justify-center gap-2 text-sm font-medium border border-slate-500 text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors disabled:opacity-50"
            >
              {checkingNow ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} className="text-yellow-400" />}
              지금 조건 체크
            </button>

            {/* 백테스트 */}
            <button
              onClick={handleBacktest}
              disabled={backtesting || buyGroup.conditions.length === 0 || sellGroup.conditions.length === 0}
              className="w-full py-2.5 flex items-center justify-center gap-2 text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {backtesting ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
              {backtesting ? '백테스트 실행 중...' : '▶ 백테스트 실행'}
            </button>

            {/* 저장 */}
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full py-2.5 flex items-center justify-center gap-2 text-sm font-semibold bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
              {saving ? '저장 중...' : editingId !== null ? '💾 저장' : '💾 새로 저장'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
