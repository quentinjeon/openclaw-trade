import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Sidebar } from '@/components/dashboard/Sidebar'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'OpenClaw Trading System',
  description: 'OpenClaw 멀티 에이전트 암호화폐 자동매매 시스템',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko" className="dark">
      <body className={`${inter.className} bg-slate-950 min-h-screen`}>
        <div className="flex h-screen overflow-hidden">
          {/* 사이드바 */}
          <Sidebar />

          {/* 메인 콘텐츠 */}
          <main className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
