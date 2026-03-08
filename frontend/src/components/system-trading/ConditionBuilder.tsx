'use client'
/**
 * 조건 빌더 컴포넌트
 * 매수/매도 조건을 시각적으로 편집하는 패널
 */
import { useState, useCallback } from 'react'
import { Plus, X, ChevronDown, Loader2, Sparkles, Wand2 } from 'lucide-react'
import type { ConditionGroup, ConditionNode, ConditionOperator } from '@/types/system_trading'
import { INDICATOR_OPTIONS, OPERATOR_OPTIONS } from '@/types/system_trading'
import { systemTradingApi } from '@/services/api'

interface ConditionBuilderProps {
  label: string                          // "매수 조건" | "매도 조건"
  color: 'green' | 'red'
  group: ConditionGroup
  onChange: (group: ConditionGroup) => void
}

const COLOR_MAP = {
  green: {
    border: 'border-green-500/30',
    bg: 'bg-green-500/5',
    badge: 'bg-green-500/20 text-green-400 border-green-500/30',
    btn: 'border-green-500/40 text-green-400 hover:bg-green-500/10',
    tag: 'text-green-400',
  },
  red: {
    border: 'border-red-500/30',
    bg: 'bg-red-500/5',
    badge: 'bg-red-500/20 text-red-400 border-red-500/30',
    btn: 'border-red-500/40 text-red-400 hover:bg-red-500/10',
    tag: 'text-red-400',
  },
}

function makeEmptyCondition(): ConditionNode {
  return {
    id: `cond_${Math.random().toString(36).slice(2, 10)}`,
    indicator_a: 'RSI',
    params_a: { period: 14 },
    operator: '<=',
    type_b: 'value',
    value_b: 30,
  }
}

// 지표에 맞는 기본 파라미터 생성
function getDefaultParams(indicatorName: string): Record<string, number> {
  const opt = INDICATOR_OPTIONS.find(o => o.value === indicatorName)
  if (!opt || opt.params.length === 0) return {}
  return Object.fromEntries(opt.params.map(p => [p.key, p.default]))
}

// 크로스 연산자 여부
function isCrossOp(op: string): boolean {
  return op === 'crosses_above' || op === 'crosses_below'
}

export function ConditionBuilder({ label, color, group, onChange }: ConditionBuilderProps) {
  const c = COLOR_MAP[color]
  const [aiText, setAiText] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiPreview, setAiPreview] = useState<ConditionGroup | null>(null)
  const [aiExplanation, setAiExplanation] = useState('')

  const side = color === 'green' ? 'buy' : 'sell'

  // 조건 추가
  const addCondition = useCallback(() => {
    onChange({
      ...group,
      conditions: [...group.conditions, makeEmptyCondition()],
    })
  }, [group, onChange])

  // 조건 삭제
  const removeCondition = useCallback((id: string) => {
    onChange({
      ...group,
      conditions: group.conditions.filter(c => c.id !== id),
    })
  }, [group, onChange])

  // 조건 수정
  const updateCondition = useCallback((id: string, patch: Partial<ConditionNode>) => {
    onChange({
      ...group,
      conditions: group.conditions.map(c =>
        c.id === id ? { ...c, ...patch } : c
      ),
    })
  }, [group, onChange])

  // AND/OR 토글
  const toggleLogic = () => {
    onChange({ ...group, logic: group.logic === 'AND' ? 'OR' : 'AND' })
  }

  // AI 조건 생성
  const handleAiGenerate = async () => {
    if (!aiText.trim()) return
    setAiLoading(true)
    setAiPreview(null)
    try {
      const result = await systemTradingApi.textToRule(aiText, side)
      if (result.success && result.group) {
        setAiPreview(result.group)
        setAiExplanation(result.explanation)
      } else {
        setAiExplanation(result.explanation)
      }
    } catch {
      setAiExplanation('조건 생성에 실패했습니다.')
    } finally {
      setAiLoading(false)
    }
  }

  const handleAiAdd = () => {
    if (!aiPreview) return
    onChange({
      ...group,
      conditions: [...group.conditions, ...aiPreview.conditions],
    })
    setAiText('')
    setAiPreview(null)
    setAiExplanation('')
  }

  return (
    <div className={`rounded-xl border ${c.border} ${c.bg} p-4`}>
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${c.tag}`}>{label}</span>
          <span className="text-xs text-slate-500">({group.conditions.length}개)</span>
        </div>
        {group.conditions.length > 1 && (
          <button
            onClick={toggleLogic}
            className={`text-xs px-2 py-1 rounded border font-medium transition-colors ${c.badge}`}
          >
            {group.logic} ▾ (클릭하여 전환)
          </button>
        )}
      </div>

      {/* 조건 목록 */}
      <div className="space-y-2 mb-3">
        {group.conditions.length === 0 && (
          <p className="text-xs text-slate-600 text-center py-3">
            아래 버튼으로 조건을 추가하세요
          </p>
        )}
        {group.conditions.map((cond, idx) => (
          <div key={cond.id} className="flex flex-col gap-1">
            {idx > 0 && (
              <div className="flex items-center gap-1 my-0.5">
                <div className="flex-1 h-px bg-slate-700/50" />
                <span className="text-[10px] text-slate-500 px-1">{group.logic}</span>
                <div className="flex-1 h-px bg-slate-700/50" />
              </div>
            )}
            <ConditionRow
              cond={cond}
              onUpdate={(patch) => updateCondition(cond.id, patch)}
              onRemove={() => removeCondition(cond.id)}
            />
          </div>
        ))}
      </div>

      {/* 조건 추가 버튼 */}
      <button
        onClick={addCondition}
        className={`w-full py-1.5 text-xs border rounded-lg flex items-center justify-center gap-1 transition-colors ${c.btn}`}
      >
        <Plus size={12} /> 조건 직접 추가
      </button>

      {/* AI 입력 구분선 */}
      <div className="flex items-center gap-2 my-3">
        <div className="flex-1 h-px bg-slate-700/50" />
        <span className="text-xs text-slate-500 flex items-center gap-1">
          <Sparkles size={11} /> AI 조건 생성
        </span>
        <div className="flex-1 h-px bg-slate-700/50" />
      </div>

      {/* AI Text-to-Rule 입력창 */}
      <div className="space-y-2">
        <textarea
          value={aiText}
          onChange={e => setAiText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) handleAiGenerate() }}
          placeholder={
            side === 'buy'
              ? '"RSI 30 이하이고 거래량 급증", "MACD 골든크로스", "볼린저 하단 이탈"...'
              : '"RSI 70 이상", "MACD 데드크로스", "5% 수익 시 청산"...'
          }
          className="w-full text-xs bg-slate-800/60 border border-slate-600 rounded-lg p-2.5 text-slate-300 placeholder-slate-600 resize-none focus:outline-none focus:border-slate-500 transition-colors"
          rows={2}
        />
        <button
          onClick={handleAiGenerate}
          disabled={!aiText.trim() || aiLoading}
          className="w-full py-1.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
        >
          {aiLoading ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
          {aiLoading ? '분석 중...' : '조건 생성 (⌘Enter)'}
        </button>

        {/* 미리보기 */}
        {aiExplanation && (
          <div className={`rounded-lg p-2.5 text-xs ${aiPreview ? 'bg-blue-500/10 border border-blue-500/20' : 'bg-red-500/10 border border-red-500/20'}`}>
            <p className={aiPreview ? 'text-blue-300' : 'text-red-400'}>
              {aiPreview ? '✅ ' : '❌ '}{aiExplanation}
            </p>
            {aiPreview && (
              <button
                onClick={handleAiAdd}
                className="mt-2 w-full py-1 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded text-xs transition-colors"
              >
                + 이 조건 추가
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── 단일 조건 행 ───────────────────────────────────────

interface ConditionRowProps {
  cond: ConditionNode
  onUpdate: (patch: Partial<ConditionNode>) => void
  onRemove: () => void
}

function ConditionRow({ cond, onUpdate, onRemove }: ConditionRowProps) {
  const needsIndicatorB = isCrossOp(cond.operator)

  const handleIndicatorAChange = (name: string) => {
    onUpdate({
      indicator_a: name,
      params_a: getDefaultParams(name),
    })
  }

  const handleOperatorChange = (op: ConditionOperator) => {
    const patch: Partial<ConditionNode> = { operator: op }
    if (isCrossOp(op)) {
      patch.type_b = 'indicator'
      patch.indicator_b = cond.indicator_b || 'MACD_SIGNAL'
      patch.params_b = cond.params_b || {}
    } else {
      patch.type_b = 'value'
    }
    onUpdate(patch)
  }

  const indOptA = INDICATOR_OPTIONS.find(o => o.value === cond.indicator_a)

  return (
    <div className="flex flex-col gap-1.5 bg-slate-800/40 rounded-lg p-2.5 border border-slate-700/50">
      <div className="flex items-start gap-1.5">
        {/* 지표 A */}
        <div className="flex-1 min-w-0">
          <select
            value={cond.indicator_a}
            onChange={e => handleIndicatorAChange(e.target.value)}
            className="w-full text-xs bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
          >
            {INDICATOR_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* 연산자 */}
        <div className="w-28 flex-shrink-0">
          <select
            value={cond.operator}
            onChange={e => handleOperatorChange(e.target.value as ConditionOperator)}
            className="w-full text-xs bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
          >
            {OPERATOR_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* 삭제 */}
        <button
          onClick={onRemove}
          className="mt-0.5 p-1 text-slate-500 hover:text-red-400 transition-colors flex-shrink-0"
        >
          <X size={13} />
        </button>
      </div>

      {/* 파라미터 A */}
      {indOptA && indOptA.params.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          {indOptA.params.map(param => (
            <div key={param.key} className="flex items-center gap-1">
              <span className="text-[10px] text-slate-500">{param.label}:</span>
              <input
                type="number"
                value={cond.params_a[param.key] ?? param.default}
                onChange={e => onUpdate({ params_a: { ...cond.params_a, [param.key]: Number(e.target.value) } })}
                className="w-16 text-xs bg-slate-700 border border-slate-600 rounded px-1.5 py-1 text-slate-200 focus:outline-none focus:border-blue-500"
              />
            </div>
          ))}
        </div>
      )}

      {/* 비교 값 (B) */}
      {!needsIndicatorB ? (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-slate-500">값:</span>
          <input
            type="number"
            step="0.1"
            value={cond.value_b ?? 0}
            onChange={e => onUpdate({ value_b: Number(e.target.value) })}
            className="w-24 text-xs bg-slate-700 border border-slate-600 rounded px-1.5 py-1 text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </div>
      ) : (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-slate-500">비교 지표:</span>
          <select
            value={cond.indicator_b || ''}
            onChange={e => onUpdate({ indicator_b: e.target.value, params_b: getDefaultParams(e.target.value) })}
            className="flex-1 text-xs bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-blue-500"
          >
            {INDICATOR_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}
