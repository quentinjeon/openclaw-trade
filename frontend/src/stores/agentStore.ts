'use client'
/**
 * 에이전트 상태 Zustand 스토어
 */
import { create } from 'zustand'
import type { Agent, AgentLog } from '@/types/agent'

interface AgentStore {
  agents: Agent[]
  logs: AgentLog[]
  setAgents: (agents: Agent[]) => void
  addLog: (log: AgentLog) => void
  setLogs: (logs: AgentLog[]) => void
  clearLogs: () => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  agents: [],
  logs: [],
  setAgents: (agents) => set({ agents }),
  addLog: (log) =>
    set((state) => ({
      // 최대 500개까지만 유지
      logs: [log, ...state.logs].slice(0, 500),
    })),
  setLogs: (logs) => set({ logs }),
  clearLogs: () => set({ logs: [] }),
}))
