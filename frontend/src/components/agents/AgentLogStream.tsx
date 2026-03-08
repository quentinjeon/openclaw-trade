'use client'
/**
 * 에이전트 로그 실시간 스트림 컴포넌트
 */
import { useEffect, useRef } from 'react'
import { Terminal } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime } from '@/lib/utils'
import type { AgentLog, AgentType } from '@/types/agent'

const LEVEL_STYLES = {
  INFO: 'text-slate-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
  DECISION: 'text-blue-400 font-semibold',
  SIGNAL: 'text-purple-400',
}

const AGENT_COLORS: Record<AgentType, string> = {
  market_analyzer: 'text-cyan-400',
  strategy: 'text-blue-400',
  risk_manager: 'text-orange-400',
  execution: 'text-green-400',
  portfolio: 'text-purple-400',
}

const AGENT_SHORT: Record<string, string> = {
  market_analyzer: 'MKT',
  strategy: 'STG',
  risk_manager: 'RSK',
  execution: 'EXE',
  portfolio: 'PFL',
}

interface AgentLogStreamProps {
  logs: AgentLog[]
  maxHeight?: string
}

export function AgentLogStream({ logs, maxHeight = '400px' }: AgentLogStreamProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  // 새 로그 추가 시 자동 스크롤 (최하단)
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Terminal size={18} className="text-green-400" />
          <span>에이전트 로그</span>
          <span className="text-sm font-normal text-slate-400">({logs.length}개)</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          ref={containerRef}
          className="bg-slate-900 rounded-lg p-4 font-mono text-xs overflow-y-auto border border-slate-700"
          style={{ maxHeight }}
        >
          {logs.length === 0 ? (
            <div className="text-slate-600 text-center py-8">
              에이전트 로그가 없습니다...
            </div>
          ) : (
            <div className="space-y-1">
              {[...logs].reverse().map((log) => (
                <div key={log.id} className="flex items-start gap-2 hover:bg-slate-800/50 px-1 rounded">
                  {/* 타임스탬프 */}
                  <span className="text-slate-600 shrink-0 w-[105px]">
                    {formatDateTime(log.created_at)}
                  </span>

                  {/* 에이전트 타입 */}
                  <span className={`shrink-0 w-[32px] font-bold ${AGENT_COLORS[log.agent_type as AgentType] || 'text-slate-400'}`}>
                    [{AGENT_SHORT[log.agent_type] || log.agent_type.toUpperCase().slice(0, 3)}]
                  </span>

                  {/* 레벨 */}
                  <span className={`shrink-0 w-[60px] ${LEVEL_STYLES[log.level as keyof typeof LEVEL_STYLES] || 'text-slate-400'}`}>
                    {log.level}
                  </span>

                  {/* 메시지 */}
                  <span className={`${LEVEL_STYLES[log.level as keyof typeof LEVEL_STYLES] || 'text-slate-300'} break-all`}>
                    {log.message}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
