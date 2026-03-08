'use client'
/**
 * 에이전트 상태 패널 컴포넌트
 * 모든 에이전트의 실시간 상태를 표시
 */
import { Activity, AlertCircle, CheckCircle, Clock, XCircle, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime } from '@/lib/utils'
import type { Agent, AgentStatus, AgentType } from '@/types/agent'

const AGENT_LABELS: Record<AgentType, string> = {
  market_analyzer: '시장 분석',
  strategy: '전략 실행',
  risk_manager: '리스크 관리',
  execution: '주문 실행',
  portfolio: '포트폴리오',
}

const AGENT_DESCRIPTIONS: Record<AgentType, string> = {
  market_analyzer: 'RSI, MACD, 볼린저 밴드 분석',
  strategy: '매매 신호 생성 (BUY/SELL/HOLD)',
  risk_manager: '포지션 크기 및 손절가 결정',
  execution: '거래소 주문 실행',
  portfolio: '수익률 및 성과 추적',
}

const STATUS_CONFIG: Record<AgentStatus, { icon: React.ReactNode; color: string; label: string }> = {
  IDLE: { icon: <Clock size={14} />, color: 'text-slate-400', label: '대기 중' },
  RUNNING: { icon: <Activity size={14} className="animate-pulse" />, color: 'text-blue-400', label: '실행 중' },
  ANALYZING: { icon: <Loader2 size={14} className="animate-spin" />, color: 'text-yellow-400', label: '분석 중' },
  EXECUTING: { icon: <Loader2 size={14} className="animate-spin" />, color: 'text-orange-400', label: '주문 중' },
  ERROR: { icon: <AlertCircle size={14} />, color: 'text-red-400', label: '오류' },
  STOPPED: { icon: <XCircle size={14} />, color: 'text-slate-600', label: '중지됨' },
}

interface AgentCardProps {
  agent: Agent
  onStart: (agentType: string) => void
  onStop: (agentType: string) => void
}

function AgentCard({ agent, onStart, onStop }: AgentCardProps) {
  const statusConfig = STATUS_CONFIG[agent.status]
  const label = AGENT_LABELS[agent.agent_type] || agent.agent_type
  const description = AGENT_DESCRIPTIONS[agent.agent_type] || ''

  return (
    <div className="flex items-center justify-between p-4 rounded-lg border border-slate-700 bg-slate-800/30 hover:bg-slate-700/30 transition-colors">
      <div className="flex items-start gap-3">
        {/* 상태 인디케이터 */}
        <div className={`mt-1 ${statusConfig.color}`}>
          {statusConfig.icon}
        </div>

        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-100">{label}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${getStatusBg(agent.status)}`}>
              {statusConfig.label}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">{description}</p>
          <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
            <span>사이클: {agent.total_cycles.toLocaleString()}</span>
            {agent.error_count > 0 && (
              <span className="text-red-400">오류: {agent.error_count}</span>
            )}
            {agent.last_run && (
              <span>마지막 실행: {formatDateTime(agent.last_run)}</span>
            )}
          </div>
        </div>
      </div>

      {/* 컨트롤 버튼 */}
      <div className="flex gap-2">
        {!agent.is_running ? (
          <button
            onClick={() => onStart(agent.agent_type)}
            className="px-3 py-1.5 text-xs bg-green-500/20 text-green-400 border border-green-500/30 rounded hover:bg-green-500/30 transition-colors"
          >
            시작
          </button>
        ) : (
          <button
            onClick={() => onStop(agent.agent_type)}
            className="px-3 py-1.5 text-xs bg-red-500/20 text-red-400 border border-red-500/30 rounded hover:bg-red-500/30 transition-colors"
          >
            중지
          </button>
        )}
      </div>
    </div>
  )
}

function getStatusBg(status: AgentStatus): string {
  const map: Record<AgentStatus, string> = {
    IDLE: 'bg-slate-700/50 text-slate-400',
    RUNNING: 'bg-blue-500/20 text-blue-400',
    ANALYZING: 'bg-yellow-500/20 text-yellow-400',
    EXECUTING: 'bg-orange-500/20 text-orange-400',
    ERROR: 'bg-red-500/20 text-red-400',
    STOPPED: 'bg-slate-700/50 text-slate-500',
  }
  return map[status] || map.IDLE
}

interface AgentStatusPanelProps {
  agents: Agent[]
  onStart: (agentType: string) => void
  onStop: (agentType: string) => void
}

export function AgentStatusPanel({ agents, onStart, onStop }: AgentStatusPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity size={18} className="text-blue-400" />
          <span>에이전트 상태</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {agents.length === 0 ? (
          <div className="text-center py-6 text-slate-500">
            <p>에이전트 정보를 불러오는 중...</p>
          </div>
        ) : (
          <div className="space-y-3">
            {agents.map((agent) => (
              <AgentCard
                key={agent.agent_id}
                agent={agent}
                onStart={onStart}
                onStop={onStop}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
