'use client'
/**
 * 포트폴리오 Zustand 스토어
 * WebSocket으로 받은 실시간 데이터를 전역 상태로 관리
 */
import { create } from 'zustand'
import type { Portfolio } from '@/types/portfolio'

interface PortfolioStore {
  portfolio: Portfolio | null
  isLoading: boolean
  lastUpdated: Date | null
  setPortfolio: (portfolio: Portfolio) => void
  setLoading: (loading: boolean) => void
}

export const usePortfolioStore = create<PortfolioStore>((set) => ({
  portfolio: null,
  isLoading: true,
  lastUpdated: null,
  setPortfolio: (portfolio) =>
    set({ portfolio, isLoading: false, lastUpdated: new Date() }),
  setLoading: (isLoading) => set({ isLoading }),
}))
