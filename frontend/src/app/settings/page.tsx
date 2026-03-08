'use client'
/**
 * 설정 페이지
 * 리스크 파라미터 및 전략 설정 관리
 */
import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { Settings, Shield, TrendingUp, Save } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { settingsApi, fetcher } from '@/services/api'
import type { RiskConfig, StrategyConfig, SystemSettings } from '@/types/agent'

function InputField({
  label,
  value,
  onChange,
  min,
  max,
  step = 0.1,
  unit,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  step?: number
  unit?: string
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-slate-300">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          min={min}
          max={max}
          step={step}
          className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {unit && <span className="text-slate-400 text-sm">{unit}</span>}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { data: settings } = useSWR<SystemSettings>(
    `${process.env.NEXT_PUBLIC_API_URL}/api/settings/`,
    fetcher,
  )

  const [riskConfig, setRiskConfig] = useState<RiskConfig>({
    max_position_size_pct: 5,
    max_open_positions: 5,
    daily_loss_limit_pct: 3,
    stop_loss_pct: 2,
    take_profit_pct: 4,
  })

  const [strategies, setStrategies] = useState<StrategyConfig[]>([])
  const [isSaving, setIsSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')

  useEffect(() => {
    if (settings?.risk) {
      setRiskConfig(settings.risk)
    }
    if (settings?.strategies) {
      setStrategies(settings.strategies)
    }
  }, [settings])

  const handleSaveRisk = async () => {
    setIsSaving(true)
    try {
      await settingsApi.updateRiskSettings(riskConfig)
      setSaveMessage('리스크 설정이 저장되었습니다')
      setTimeout(() => setSaveMessage(''), 3000)
    } catch (err) {
      setSaveMessage('저장 실패')
    } finally {
      setIsSaving(false)
    }
  }

  const handleToggleStrategy = async (index: number) => {
    const updated = [...strategies]
    updated[index] = { ...updated[index], enabled: !updated[index].enabled }
    setStrategies(updated)

    try {
      await settingsApi.updateStrategySettings(updated[index].name, updated[index])
    } catch (err) {
      console.error('전략 설정 업데이트 실패:', err)
    }
  }

  const STRATEGY_LABELS: Record<string, string> = {
    rsi_reversal: 'RSI 역추세',
    macd_crossover: 'MACD 크로스오버',
    bollinger_bands: '볼린저 밴드',
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto flex-1">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">설정</h1>
        <p className="text-sm text-slate-400 mt-1">리스크 파라미터 및 전략 설정</p>
      </div>

      {/* 시스템 정보 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings size={18} className="text-slate-400" />
            시스템 정보
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-xs text-slate-400">거래 모드</p>
              <p className={`font-semibold mt-1 ${settings?.paper_trading ? 'text-purple-400' : 'text-green-400'}`}>
                {settings?.paper_trading ? '페이퍼트레이딩' : '실거래'}
              </p>
            </div>
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-xs text-slate-400">기본 거래소</p>
              <p className="font-semibold mt-1 text-slate-100 uppercase">
                {settings?.default_exchange || '-'}
              </p>
            </div>
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-xs text-slate-400">거래 심볼</p>
              <p className="font-semibold mt-1 text-slate-100 text-sm">
                {settings?.default_symbols?.join(', ') || '-'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 리스크 설정 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield size={18} className="text-orange-400" />
            리스크 관리 설정
          </CardTitle>
          <CardDescription>
            리스크 파라미터를 보수적으로 설정하세요. 처음에는 최대 포지션 5% 권장
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <InputField
              label="최대 포지션 크기"
              value={riskConfig.max_position_size_pct}
              onChange={(v) => setRiskConfig({ ...riskConfig, max_position_size_pct: v })}
              min={1}
              max={50}
              unit="%"
            />
            <InputField
              label="최대 동시 포지션 수"
              value={riskConfig.max_open_positions}
              onChange={(v) => setRiskConfig({ ...riskConfig, max_open_positions: v })}
              min={1}
              max={20}
              step={1}
              unit="개"
            />
            <InputField
              label="일일 손실 한도"
              value={riskConfig.daily_loss_limit_pct}
              onChange={(v) => setRiskConfig({ ...riskConfig, daily_loss_limit_pct: v })}
              min={0.5}
              max={20}
              unit="%"
            />
            <InputField
              label="기본 손절가"
              value={riskConfig.stop_loss_pct}
              onChange={(v) => setRiskConfig({ ...riskConfig, stop_loss_pct: v })}
              min={0.5}
              max={10}
              unit="%"
            />
            <InputField
              label="기본 익절가"
              value={riskConfig.take_profit_pct}
              onChange={(v) => setRiskConfig({ ...riskConfig, take_profit_pct: v })}
              min={0.5}
              max={30}
              unit="%"
            />
          </div>

          <div className="mt-6 flex items-center gap-4">
            <button
              onClick={handleSaveRisk}
              disabled={isSaving}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Save size={16} />
              {isSaving ? '저장 중...' : '저장'}
            </button>
            {saveMessage && (
              <span className="text-sm text-green-400">{saveMessage}</span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 전략 설정 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp size={18} className="text-green-400" />
            매매 전략 설정
          </CardTitle>
          <CardDescription>
            활성화된 전략의 신호를 합산하여 최종 매매 신호를 결정합니다
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {strategies.map((strategy, index) => (
              <div
                key={strategy.name}
                className="flex items-center justify-between p-4 bg-slate-800 rounded-lg border border-slate-700"
              >
                <div>
                  <p className="font-medium text-slate-100">
                    {STRATEGY_LABELS[strategy.name] || strategy.name}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {strategy.description || JSON.stringify(strategy.params)}
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <span className={`text-sm ${strategy.enabled ? 'text-green-400' : 'text-slate-500'}`}>
                    {strategy.enabled ? '활성화' : '비활성화'}
                  </span>
                  <button
                    onClick={() => handleToggleStrategy(index)}
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      strategy.enabled ? 'bg-green-500' : 'bg-slate-600'
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                        strategy.enabled ? 'translate-x-6' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
