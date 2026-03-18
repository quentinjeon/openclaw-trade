'use client'
/**
 * 백테스트 기반 종목 스캔 · 점수 · 자동매수 설정
 */
import { useState, useEffect, useCallback } from 'react'
import {
  RefreshCw,
  Loader2,
  Zap,
  ShieldAlert,
  Play,
  Save,
} from 'lucide-react'
import { picksApi } from '@/services/api'
import type { PickScannerConfig, PickResultRow } from '@/types/picks'
import { formatPercent } from '@/lib/utils'

export default function PicksPage() {
  const [cfg, setCfg] = useState<PickScannerConfig | null>(null)
  const [templates, setTemplates] = useState<{ key: string; name: string }[]>([])
  const [results, setResults] = useState<PickResultRow[]>([])
  const [loadingCfg, setLoadingCfg] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [saving, setSaving] = useState(false)
  const [autoBuyRunning, setAutoBuyRunning] = useState(false)
  const [lastScanMsg, setLastScanMsg] = useState<string | null>(null)
  const [symbolsText, setSymbolsText] = useState('')

  const load = useCallback(async () => {
    setLoadingCfg(true)
    try {
      const d = await picksApi.getConfig()
      setCfg(d.config)
      setTemplates(d.template_options || [])
      setSymbolsText((d.config.symbols || []).join('\n'))
    } catch {
      setLastScanMsg('설정 로드 실패')
    } finally {
      setLoadingCfg(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleSave = async () => {
    if (!cfg) return
    setSaving(true)
    try {
      const symbols = symbolsText
        .split(/[\n,]+/)
        .map((s) => s.trim())
        .filter(Boolean)
      await picksApi.putConfig({
        ...cfg,
        symbols: symbols.length ? symbols : cfg.symbols,
      })
      await load()
      setLastScanMsg('설정 저장됨')
    } catch {
      setLastScanMsg('저장 실패')
    } finally {
      setSaving(false)
    }
  }

  const handleScan = async () => {
    setScanning(true)
    setLastScanMsg(null)
    try {
      const syms = symbolsText
        .split(/[\n,]+/)
        .map((s) => s.trim())
        .filter(Boolean)
      const res = await picksApi.scan({
        symbols: syms.length ? syms : undefined,
        timeframe: cfg?.timeframe,
        candle_limit: cfg?.candle_limit,
        template_key: cfg?.template_key,
        condition_id: cfg?.condition_id ?? undefined,
      })
      setResults(res.results)
      setLastScanMsg(`${res.count}개 심볼 스캔 완료 (${res.timeframe})`)
    } catch {
      setLastScanMsg('스캔 실패 (백엔드·거래소 연결 확인)')
    } finally {
      setScanning(false)
    }
  }

  const handleAutoBuyOnce = async (force: boolean) => {
    setAutoBuyRunning(true)
    try {
      const r = await picksApi.autoBuyOnce(force)
      const parts = [
        r.skipped_reason || (r.attempted ? `승인 ${r.bought}건` : ''),
        ...(r.details || []).map((d) => `${d.symbol}: ${d.action}${d.reason ? ` (${d.reason})` : ''}`),
      ].filter(Boolean)
      setLastScanMsg(parts.join(' | ') || JSON.stringify(r))
    } catch {
      setLastScanMsg('자동매수 요청 실패')
    } finally {
      setAutoBuyRunning(false)
    }
  }

  if (loadingCfg || !cfg) {
    return (
      <div className="flex items-center justify-center min-h-[40vh] text-slate-400">
        <Loader2 className="animate-spin mr-2" size={20} />
        로딩 중…
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Zap className="text-amber-400" />
          백테스트 종목 스캐너
        </h1>
        <p className="text-slate-400 mt-1 text-sm">
          동일 전략 템플릿으로 과거 구간 백테스트 → 점수화. 설정한 최저 점수 이상이면 자동매수(리스크
          매니저 통과 시) 가능합니다.
        </p>
      </div>

      {lastScanMsg && (
        <div className="rounded-lg bg-slate-800 border border-slate-600 px-4 py-2 text-sm text-slate-300">
          {lastScanMsg}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-5 space-y-4">
          <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
            <ShieldAlert size={18} className="text-orange-400" />
            자동매수 설정
          </h2>
          <label className="flex items-center gap-2 text-slate-300 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={cfg.auto_buy_enabled}
              onChange={(e) => setCfg({ ...cfg, auto_buy_enabled: e.target.checked })}
              className="rounded border-slate-600"
            />
            스케줄 자동매수 활성화 (백그라운드, 간격은 아래 분 단위)
          </label>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <label className="text-slate-500 block mb-1">최저 점수 (0~100)</label>
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={cfg.min_score}
                onChange={(e) => setCfg({ ...cfg, min_score: Number(e.target.value) })}
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-100"
              />
            </div>
            <div>
              <label className="text-slate-500 block mb-1">스캔 간격 (분)</label>
              <input
                type="number"
                min={5}
                max={1440}
                value={cfg.scan_interval_minutes}
                onChange={(e) =>
                  setCfg({ ...cfg, scan_interval_minutes: Number(e.target.value) })
                }
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-100"
              />
            </div>
            <div>
              <label className="text-slate-500 block mb-1">타임프레임</label>
              <select
                value={cfg.timeframe}
                onChange={(e) => setCfg({ ...cfg, timeframe: e.target.value })}
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-100"
              >
                {['5m', '15m', '1h', '4h', '1d'].map((tf) => (
                  <option key={tf} value={tf}>
                    {tf}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-slate-500 block mb-1">캔들 개수</label>
              <input
                type="number"
                min={50}
                max={1000}
                value={cfg.candle_limit}
                onChange={(e) => setCfg({ ...cfg, candle_limit: Number(e.target.value) })}
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-100"
              />
            </div>
          </div>
          <div>
            <label className="text-slate-500 text-sm block mb-1">백테스트 전략 템플릿</label>
            <select
              value={cfg.template_key}
              onChange={(e) => setCfg({ ...cfg, template_key: e.target.value })}
              className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-100 text-sm"
            >
              {templates.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-slate-500 text-sm block mb-1">
              시스템 조건식 ID (비우면 템플릿 사용)
            </label>
            <input
              type="number"
              min={1}
              placeholder="예: 1"
              value={cfg.condition_id ?? ''}
              onChange={(e) => {
                const v = e.target.value
                setCfg({
                  ...cfg,
                  condition_id: v === '' ? null : Number(v),
                })
              }}
              className="w-full max-w-xs bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-100 text-sm"
            />
          </div>
          <label className="flex items-center gap-2 text-slate-300 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={cfg.require_live_buy_signal}
              onChange={(e) => setCfg({ ...cfg, require_live_buy_signal: e.target.checked })}
              className="rounded border-slate-600"
            />
            현재 봉에서 매수 조건 충족 시에만 자동매수 (권장)
          </label>
          <div>
            <label className="text-slate-500 text-sm block mb-1">회당 최대 매수 종목 수</label>
            <input
              type="number"
              min={1}
              max={10}
              value={cfg.max_auto_buys_per_scan}
              onChange={(e) =>
                setCfg({ ...cfg, max_auto_buys_per_scan: Number(e.target.value) })
              }
              className="w-32 bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-100"
            />
          </div>
          <div>
            <label className="text-slate-500 text-sm block mb-1">스캔 심볼 (줄바꿈 구분)</label>
            <textarea
              value={symbolsText}
              onChange={(e) => setSymbolsText(e.target.value)}
              rows={5}
              className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-100 text-sm font-mono"
              placeholder="BTC/USDT&#10;ETH/USDT"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50"
            >
              {saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
              설정 저장
            </button>
            <button
              type="button"
              onClick={handleScan}
              disabled={scanning}
              className="flex items-center gap-1 px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-100 text-sm"
            >
              {scanning ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
              지금 스캔
            </button>
            <button
              type="button"
              onClick={() => handleAutoBuyOnce(false)}
              disabled={autoBuyRunning}
              className="flex items-center gap-1 px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-sm disabled:opacity-50"
            >
              {autoBuyRunning ? <Loader2 className="animate-spin" size={16} /> : <Play size={16} />}
              자동매수 1회 (설정 켜짐 시)
            </button>
            <button
              type="button"
              onClick={() => handleAutoBuyOnce(true)}
              disabled={autoBuyRunning}
              className="px-3 py-2 rounded-lg border border-amber-600/50 text-amber-400 text-xs hover:bg-amber-900/20"
            >
              강제 1회 (테스트)
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-5">
          <h2 className="text-lg font-semibold text-slate-200 mb-3">점수 기준 안내</h2>
          <ul className="text-sm text-slate-400 space-y-2 list-disc pl-4">
            <li>선택한 템플릿과 동일한 매수·매도 규칙으로 캔들 구간 백테스트를 돌립니다.</li>
            <li>승률, 누적 수익률, MDD, 거래 횟수를 합산해 0~100 점수를 부여합니다.</li>
            <li>점수는 과거 성과일 뿐이며, 실제 수익을 보장하지 않습니다.</li>
            <li>자동매수는 페이퍼/실계좌 모두 RiskManager(포지션 수·잔고 등)를 통과해야 체결됩니다.</li>
          </ul>
        </div>
      </div>

      <div className="rounded-xl border border-slate-700 overflow-hidden">
        <div className="bg-slate-800 px-4 py-2 text-slate-200 font-medium text-sm">스캔 결과</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-900 text-slate-500 text-left">
              <tr>
                <th className="px-3 py-2">심볼</th>
                <th className="px-3 py-2">점수</th>
                <th className="px-3 py-2">승률</th>
                <th className="px-3 py-2">누적%</th>
                <th className="px-3 py-2">MDD</th>
                <th className="px-3 py-2">거래수</th>
                <th className="px-3 py-2">매수신호</th>
                <th className="px-3 py-2">비고</th>
              </tr>
            </thead>
            <tbody>
              {results.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-slate-500">
                    스캔을 실행하면 결과가 표시됩니다.
                  </td>
                </tr>
              ) : (
                results.map((r) => (
                  <tr
                    key={r.symbol}
                    className="border-t border-slate-800 hover:bg-slate-800/40 text-slate-300"
                  >
                    <td className="px-3 py-2 font-mono">{r.symbol}</td>
                    <td className="px-3 py-2">
                      <span
                        className={
                          r.score >= (cfg?.min_score ?? 60)
                            ? 'text-emerald-400 font-semibold'
                            : 'text-slate-400'
                        }
                      >
                        {r.score}
                      </span>
                    </td>
                    <td className="px-3 py-2">{formatPercent(r.win_rate)}</td>
                    <td className="px-3 py-2">{formatPercent(r.total_return_pct)}</td>
                    <td className="px-3 py-2 text-red-400">{formatPercent(r.max_drawdown_pct)}</td>
                    <td className="px-3 py-2">{r.total_trades}</td>
                    <td className="px-3 py-2">
                      {r.live_buy_signal ? (
                        <span className="text-emerald-400">ON</span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-500 text-xs max-w-xs truncate" title={r.score_detail}>
                      {r.score_detail}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
