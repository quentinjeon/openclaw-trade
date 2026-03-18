'use client'
/**
 * 사이드바 네비게이션 컴포넌트
 */
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  BarChart2,
  Activity,
  History,
  Settings,
  LineChart,
  Zap,
  Wallet,
  BotMessageSquare,
  Sparkles,
} from 'lucide-react'
import useSWR from 'swr'
import { cn } from '@/lib/utils'
import { fetcher } from '@/services/api'

const navItems = [
  { href: '/', icon: LayoutDashboard, label: '대시보드' },
  { href: '/market', icon: LineChart, label: '시황 분석' },
  { href: '/system-trading', icon: BotMessageSquare, label: '시스템 트레이딩' },
  { href: '/picks', icon: Sparkles, label: '종목 스캔' },
  { href: '/portfolio', icon: BarChart2, label: '포트폴리오' },
  { href: '/wallet', icon: Wallet, label: '내 지갑' },
  { href: '/agents', icon: Activity, label: '에이전트' },
  { href: '/trades', icon: History, label: '거래 내역' },
  { href: '/settings', icon: Settings, label: '설정' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { data: settings } = useSWR<{ paper_trading?: boolean }>(
    `${process.env.NEXT_PUBLIC_API_URL}/api/settings/`,
    fetcher,
    { refreshInterval: 60000 },
  )
  const live = settings?.paper_trading === false

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-700 flex flex-col">
      {/* 로고 */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <Zap size={20} className="text-white" />
          </div>
          <div>
            <h1 className="font-bold text-slate-100">OpenClaw</h1>
            <p className="text-xs text-slate-400">Trading System</p>
          </div>
        </div>
      </div>

      {/* 네비게이션 */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100',
              )}
            >
              <item.icon size={18} />
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* 하단 상태 */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-800 rounded-lg">
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          <span className="text-xs text-slate-400">시스템 운영 중</span>
          <span
            className={`ml-auto text-xs font-medium ${live ? 'text-emerald-400' : 'text-amber-400'}`}
          >
            {live ? 'LIVE' : 'PAPER'}
          </span>
        </div>
      </div>
    </aside>
  )
}
