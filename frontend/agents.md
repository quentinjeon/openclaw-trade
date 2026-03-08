# 프론트엔드 컴포넌트 및 구조 명세

> **규칙**: 컴포넌트 추가/변경 시 이 파일을 반드시 업데이트하세요.

## 기술 스택
- **프레임워크**: Next.js 14 (App Router)
- **언어**: TypeScript (strict mode)
- **스타일링**: Tailwind CSS (다크 테마 기본)
- **상태관리**: Zustand (전역) + SWR (서버 상태)
- **실시간**: WebSocket (native)
- **아이콘**: Lucide React

## 컴포넌트 구조

```
src/
├── app/                         # Next.js App Router 페이지
│   ├── layout.tsx               # 루트 레이아웃 + Sidebar (flex, padding-free)
│   ├── page.tsx                 # 대시보드 (메인)
│   ├── market/page.tsx          # 시황 분석 (캔들차트 고도화 - 3패널 레이아웃)
│   ├── portfolio/page.tsx       # 포트폴리오 상세
│   ├── agents/page.tsx          # 에이전트 모니터링
│   ├── trades/page.tsx          # 거래 내역
│   └── settings/page.tsx        # 설정
│
├── components/
│   ├── ui/                      # 기본 UI 컴포넌트
│   │   └── card.tsx             # Card, CardHeader, CardContent...
│   ├── market/                  # 시황 분석 전용
│   │   └── CandleChart.tsx      # lightweight-charts 캔들 차트 (MA/BB/거래량)
│   │
│   ├── dashboard/               # 대시보드 전용
│   │   ├── Sidebar.tsx          # 사이드바 네비게이션
│   │   ├── PortfolioSummary.tsx # 포트폴리오 요약 (4개 메트릭 카드)
│   │   └── PositionTable.tsx    # 보유 포지션 테이블
│   │
│   ├── agents/                  # 에이전트 모니터링
│   │   ├── AgentStatusPanel.tsx # 에이전트 상태 카드 목록
│   │   └── AgentLogStream.tsx   # 실시간 로그 터미널
│   │
│   └── trading/                 # 거래 관련
│       └── TradeHistoryTable.tsx # 거래 내역 테이블
│
├── hooks/
│   └── useWebSocket.ts          # WebSocket 커스텀 훅
│
├── stores/
│   ├── portfolioStore.ts        # 포트폴리오 Zustand 스토어
│   └── agentStore.ts            # 에이전트 Zustand 스토어
│
├── services/
│   └── api.ts                   # API 클라이언트 (portfolioApi, tradeApi, agentApi, settingsApi)
│
├── types/
│   ├── portfolio.ts             # Portfolio, Position 타입
│   ├── agent.ts                 # Agent, AgentLog, MarketSignal, ...
│   └── trade.ts                 # Trade, TradeListResponse 타입
│
└── lib/
    └── utils.ts                 # 공통 유틸 (formatUSD, formatPercent, ...)
```

---

## 페이지 상세

### 대시보드 (`/`)
- 포트폴리오 요약 4개 메트릭 카드 (총 자산, 수익률, 오늘 손익, 승률)
- 에이전트 상태 패널 (시작/중지 버튼 포함)
- 보유 포지션 테이블
- 실시간 에이전트 로그 스트림 (터미널 스타일)
- 최근 거래 내역

**실시간 데이터**:
- SWR으로 초기 데이터 로드 (5~30초 갱신)
- WebSocket으로 실시간 업데이트

### 포트폴리오 (`/portfolio`)
- 전체 포트폴리오 요약
- 현금/포지션 가치 분석
- 보유 포지션 상세
- 전체 청산 버튼 (긴급 시)

### 에이전트 (`/agents`)
- 5개 에이전트 상태 패널 (시작/중지)
- 상세 로그 스트림 (200개)

### 거래 내역 (`/trades`)
- 전체 거래 목록 (100개)
- 심볼, 구분, 수량, 가격, 손익, 전략 표시

### 설정 (`/settings`)
- 리스크 파라미터 설정
- 전략 활성화/비활성화 토글

---

## 실시간 데이터 흐름

```
Backend WebSocket
    ↓ /ws/portfolio → useWebSocket('portfolio')
    ↓ /ws/agents   → useWebSocket('agents')
    ↓ /ws/trades   → useWebSocket('trades')

useWebSocket → Zustand Store (usePortfolioStore, useAgentStore)
                           ↓
                    React Components (자동 리렌더)
```

---

## API 클라이언트 (`services/api.ts`)

| 모듈 | 메서드 | 설명 |
|------|--------|------|
| `portfolioApi` | `getPortfolio()` | 포트폴리오 조회 |
| `tradeApi` | `getTrades()` | 거래 내역 |
| `tradeApi` | `closeAllPositions()` | 전체 청산 |
| `agentApi` | `getAgents()` | 에이전트 상태 |
| `agentApi` | `getAgentLogs()` | 로그 조회 |
| `agentApi` | `startAgent(type)` | 에이전트 시작 |
| `agentApi` | `stopAgent(type)` | 에이전트 중지 |
| `settingsApi` | `getSettings()` | 설정 조회 |
| `settingsApi` | `updateRiskSettings()` | 리스크 설정 |
| `settingsApi` | `updateStrategySettings()` | 전략 설정 |

---

## UI 규칙

### 색상 체계
- **수익**: `text-green-400` (#22c55e)
- **손실**: `text-red-400` (#ef4444)
- **중립**: `text-slate-400` (#94a3b8)
- **배경**: `bg-slate-950` (최상위), `bg-slate-900` (사이드바), `bg-slate-800/50` (카드)
- **페이퍼트레이딩**: `text-purple-400` (구분 표시)

### 공통 유틸 (`lib/utils.ts`)
- `formatUSD(value)`: USD 포맷
- `formatPercent(value)`: % 포맷 (±부호)
- `formatAmount(value)`: 코인 수량 포맷
- `formatDateTime(dateStr)`: 날짜/시간 포맷
- `getPnlColor(value)`: 손익 색상 클래스

---

*최종 업데이트: 2026-03-08*  
*버전: 1.0.0*
