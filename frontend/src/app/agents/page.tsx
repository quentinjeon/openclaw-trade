'use client'
/**
 * 에이전트 모니터링 페이지
 */
import useSWR from 'swr'
import { AgentStatusPanel } from '@/components/agents/AgentStatusPanel'
import { AgentLogStream } from '@/components/agents/AgentLogStream'
import { agentApi, fetcher } from '@/services/api'
import type { Agent, AgentLog } from '@/types/agent'

export default function AgentsPage() {
  const { data: agents = [] } = useSWR<Agent[]>(
    `${process.env.NEXT_PUBLIC_API_URL}/api/agents/`,
    fetcher,
    { refreshInterval: 5000 },
  )

  const { data: logs = [] } = useSWR<AgentLog[]>(
    `${process.env.NEXT_PUBLIC_API_URL}/api/agents/logs?limit=200`,
    fetcher,
    { refreshInterval: 10000 },
  )

  const handleStart = async (agentType: string) => {
    await agentApi.startAgent(agentType)
  }

  const handleStop = async (agentType: string) => {
    await agentApi.stopAgent(agentType)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">에이전트 모니터링</h1>
        <p className="text-sm text-slate-400 mt-1">OpenClaw 멀티 에이전트 상태 및 활동 로그</p>
      </div>

      <AgentStatusPanel
        agents={agents}
        onStart={handleStart}
        onStop={handleStop}
      />

      <AgentLogStream logs={logs} maxHeight="600px" />
    </div>
  )
}
