'use client'
/**
 * CandleChart 컴포넌트
 * TradingView Lightweight Charts 캔들스틱 차트
 * MA20/50/200, 볼린저밴드 오버레이 + 하단 거래량 바 포함
 *
 * 주의: useEffect cleanup이 chart.remove()를 처리하므로
 *       effect 시작 시점에 이미 dispose된 객체를 재호출하지 않도록
 *       ref 없이 클로저로만 참조합니다.
 */
import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from 'lightweight-charts'

export interface OHLCVCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface CandleChartProps {
  candles: OHLCVCandle[]
  showMA?: boolean
  showBB?: boolean
  height?: number
}

// ── 이동평균 계산 ──────────────────────────────────────
function calcMA(data: OHLCVCandle[], period: number) {
  return data
    .map((c, i) => {
      if (i < period - 1) return null
      const slice = data.slice(i - period + 1, i + 1)
      const avg = slice.reduce((sum, x) => sum + x.close, 0) / period
      return { time: c.time as number, value: avg }
    })
    .filter(Boolean) as { time: number; value: number }[]
}

// ── 볼린저밴드 계산 ──────────────────────────────────
function calcBollinger(data: OHLCVCandle[], period = 20, stdDev = 2) {
  const upper: { time: number; value: number }[] = []
  const lower: { time: number; value: number }[] = []

  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1)
    const avg = slice.reduce((s, x) => s + x.close, 0) / period
    const variance = slice.reduce((s, x) => s + Math.pow(x.close - avg, 2), 0) / period
    const std = Math.sqrt(variance)
    upper.push({ time: data[i].time, value: avg + stdDev * std })
    lower.push({ time: data[i].time, value: avg - stdDev * std })
  }
  return { upper, lower }
}

export default function CandleChart({
  candles,
  showMA = true,
  showBB = true,
  height = 480,
}: CandleChartProps) {
  // DOM 컨테이너만 ref로 관리, 차트 인스턴스는 클로저로 처리
  const mainRef = useRef<HTMLDivElement>(null)
  const volumeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mainEl = mainRef.current
    const volEl = volumeRef.current
    if (!mainEl || !volEl || candles.length === 0) return

    const CHART_HEIGHT = height - 110
    const VOL_HEIGHT = 100

    // ── 메인 캔들 차트 ────────────────────────────────
    const chart = createChart(mainEl, {
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#1e293b' },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
        secondsVisible: false,
      },
      width: mainEl.clientWidth,
      height: CHART_HEIGHT,
    })

    // 캔들 시리즈
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#3b82f6',
      downColor: '#ef4444',
      borderUpColor: '#3b82f6',
      borderDownColor: '#ef4444',
      wickUpColor: '#3b82f6',
      wickDownColor: '#ef4444',
    })
    candleSeries.setData(
      candles.map(c => ({ time: c.time as number, open: c.open, high: c.high, low: c.low, close: c.close }))
    )

    // 이동평균선
    if (showMA) {
      const ma20 = chart.addSeries(LineSeries, { color: '#eab308', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
      ma20.setData(calcMA(candles, 20))

      const ma50 = chart.addSeries(LineSeries, { color: '#f97316', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
      ma50.setData(calcMA(candles, 50))

      if (candles.length >= 200) {
        const ma200 = chart.addSeries(LineSeries, { color: '#a855f7', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
        ma200.setData(calcMA(candles, 200))
      }
    }

    // 볼린저밴드
    if (showBB && candles.length >= 20) {
      const { upper, lower } = calcBollinger(candles)
      const bbUp = chart.addSeries(LineSeries, { color: '#64748b', lineWidth: 1, lineStyle: 1, priceLineVisible: false, lastValueVisible: false })
      bbUp.setData(upper)
      const bbLow = chart.addSeries(LineSeries, { color: '#64748b', lineWidth: 1, lineStyle: 1, priceLineVisible: false, lastValueVisible: false })
      bbLow.setData(lower)
    }

    chart.timeScale().fitContent()

    // ── 거래량 서브 차트 ──────────────────────────────
    const volumeChart = createChart(volEl, {
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      rightPriceScale: { borderColor: '#1e293b' },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
        secondsVisible: false,
      },
      width: volEl.clientWidth,
      height: VOL_HEIGHT,
    })

    const volSeries = volumeChart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })
    volSeries.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0 } })
    volSeries.setData(
      candles.map(c => ({
        time: c.time as number,
        value: c.volume,
        color: c.close >= c.open ? '#3b82f680' : '#ef444480',
      }))
    )
    volumeChart.timeScale().fitContent()

    // ── 리사이즈 ─────────────────────────────────────
    const handleResize = () => {
      if (mainEl) chart.applyOptions({ width: mainEl.clientWidth })
      if (volEl) volumeChart.applyOptions({ width: volEl.clientWidth })
    }
    window.addEventListener('resize', handleResize)

    // ── 클린업: chart.remove()를 cleanup에서만 호출 ───
    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      volumeChart.remove()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, showMA, showBB, height])

  return (
    <div className="w-full" style={{ height }}>
      <div ref={mainRef} className="w-full" style={{ height: height - 110 }} />
      <div ref={volumeRef} className="w-full" style={{ height: 100 }} />
    </div>
  )
}
