'use client'
/**
 * 메인 대시보드 페이지
 * 포트폴리오 요약, 에이전트 상태, 실시간 로그 표시
 */
import { useEffect } from 'react'
import useSWR from 'swr'
import { Activity, AlertTriangle, RefreshCw } from 'lucide-react'

import { PortfolioSummary } from '@/components/dashboard/PortfolioSummary'
import { PositionTable } from '@/components/dashboard/PositionTable'
import { AgentStatusPanel } from '@/components/agents/AgentStatusPanel'
import { AgentLogStream } from '@/components/agents/AgentLogStream'
import { TradeHistoryTable } from '@/components/trading/TradeHistoryTable'
import { PendingOrderApproval } from '@/components/dashboard/PendingOrderApproval'
import { PipelineOpportunityCards } from '@/components/dashboard/PipelineOpportunityCards'
import { TradingScorePanel } from '@/components/dashboard/TradingScorePanel'

import { useWebSocket } from '@/hooks/useWebSocket'
import { usePortfolioStore } from '@/stores/portfolioStore'
import { useAgentStore } from '@/stores/agentStore'
import { agentApi, fetcher } from '@/services/api'
import type { Portfolio } from '@/types/portfolio'
import type { AgentLog } from '@/types/agent'

export default function DashboardPage() {
  const { setPortfolio, portfolio, isLoading } = usePortfolioStore()
  const { agents, setAgents, logs, setLogs, addLog } = useAgentStore()

  // ────────────────────────────────────────
  // SWR 초기 데이터 로드
  // ────────────────────────────────────────
  const { data: initialPortfolio } = useSWR<Portfolio>(
    `${process.env.NEXT_PUBLIC_API_URL}/api/portfolio/`,
    fetcher,
    { refreshInterval: 10000 },
  )

  const { data: initialAgents } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL}/api/agents/`,
    fetcher,
    { refreshInterval: 5000 },
  )

  const { data: initialLogs } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL}/api/agents/logs?limit=100`,
    fetcher,
    { refreshInterval: 30000 },
  )

  const { data: tradesData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL}/api/trades/?limit=20`,
    fetcher,
    { refreshInterval: 10000 },
  )

  // 초기 데이터 스토어에 설정
  useEffect(() => {
    if (initialPortfolio) setPortfolio(initialPortfolio)
  }, [initialPortfolio, setPortfolio])

  useEffect(() => {
    if (initialAgents) setAgents(initialAgents as Parameters<typeof setAgents>[0])
  }, [initialAgents, setAgents])

  useEffect(() => {
    if (initialLogs) setLogs(initialLogs as AgentLog[])
  }, [initialLogs, setLogs])

  // ────────────────────────────────────────
  // WebSocket 실시간 업데이트
  // ────────────────────────────────────────
  const { lastMessage: portfolioMsg } = useWebSocket<Portfolio>('portfolio')
  const { lastMessage: agentMsg } = useWebSocket<AgentLog>('agents')

  useEffect(() => {
    if (portfolioMsg?.data) {
      setPortfolio(portfolioMsg.data)
    }
  }, [portfolioMsg, setPortfolio])

  useEffect(() => {
    if (agentMsg?.data && agentMsg.type === 'agent_log') {
      addLog(agentMsg.data as AgentLog)
    }
  }, [agentMsg, addLog])

  // ────────────────────────────────────────
  // 에이전트 컨트롤 핸들러
  // ────────────────────────────────────────
  const handleStartAgent = async (agentType: string) => {
    try {
      await agentApi.startAgent(agentType)
    } catch (err) {
      console.error('에이전트 시작 실패:', err)
    }
  }

  const handleStopAgent = async (agentType: string) => {
    try {
      await agentApi.stopAgent(agentType)
    } catch (err) {
      console.error('에이전트 중지 실패:', err)
    }
  }

  const trades = (tradesData as { trades: Parameters<typeof TradeHistoryTable>[0]['trades'] } | undefined)?.trades ?? []

  return (
    <div className="p-6 space-y-6 overflow-y-auto flex-1">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">대시보드</h1>
          <p className="text-sm text-slate-400 mt-1">OpenClaw 암호화폐 자동매매 시스템</p>
        </div>

        {portfolio?.live_trading ? (
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/35 rounded-lg">
            <div className="flex items-center gap-2">
              <Activity size={16} className="text-emerald-400 shrink-0" />
              <span className="text-sm text-emerald-200 font-semibold">실거래 · 거래소 잔고 동기화</span>
            </div>
            <span className="text-xs text-slate-400 sm:border-l sm:border-slate-600 sm:pl-3">
              현금(스테이블) {portfolio.cash_usd.toLocaleString(undefined, { maximumFractionDigits: 2 })} USDT 상당 · 총자산{' '}
              {portfolio.total_value_usd.toLocaleString(undefined, { maximumFractionDigits: 2 })} USD
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-4 py-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <AlertTriangle size={16} className="text-amber-400" />
            <span className="text-sm text-amber-200">시뮬레이션(페이퍼) — .env 에 PAPER_TRADING=true</span>
          </div>
        )}
      </div>

      {/* 포트폴리오 요약 */}
      <PortfolioSummary portfolio={portfolio} isLoading={isLoading} />

      {/* 매수·매도·보유 점수 & 자금 비중 */}
      <TradingScorePanel liveTrading={portfolio?.live_trading ?? false} />

      {/* 수동 주문 승인 */}
      <PendingOrderApproval />

      {/* 백테스트 기반 단기 파이프라인 (조건 맞을 때만 표시) */}
      <PipelineOpportunityCards />

      {/* 에이전트 상태 + 보유 포지션 */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <AgentStatusPanel
          agents={agents}
          onStart={handleStartAgent}
          onStop={handleStopAgent}
        />
        <PositionTable positions={portfolio?.positions || {}} />
      </div>

      {/* 에이전트 로그 */}
      <AgentLogStream logs={logs} maxHeight="350px" />

      {/* 최근 거래 내역 */}
      <TradeHistoryTable trades={trades} />
    </div>
  )
}
