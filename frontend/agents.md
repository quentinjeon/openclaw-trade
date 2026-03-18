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
│   ├── system-trading/page.tsx  # 시스템 트레이딩 (조건식 + 백테스트)
│   ├── picks/page.tsx           # 종목 스캔 (백테스트 점수 + 자동매수 설정)
│   ├── portfolio/page.tsx       # 포트폴리오 상세
│   ├── wallet/page.tsx          # 내 지갑 (Binance 계좌 잔액)
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
│   │   ├── Sidebar.tsx          # 사이드바 네비게이션 (내 지갑 메뉴 포함)
│   │   ├── PortfolioSummary.tsx # 포트폴리오 요약 (4개 메트릭 카드)
│   │   └── PositionTable.tsx    # 보유 포지션 테이블
│   │
│   ├── agents/                  # 에이전트 모니터링
│   │   ├── AgentStatusPanel.tsx # 에이전트 상태 카드 목록
│   │   └── AgentLogStream.tsx   # 실시간 로그 터미널
│   │
│   ├── wallet/                  # 내 지갑 전용
│   │   ├── WalletSummaryCards.tsx # 상단 4개 요약 카드
│   │   └── AssetTable.tsx         # 코인 자산 테이블 (프로그레스 바)
│   │
│   ├── system-trading/          # 시스템 트레이딩 전용
│   │   ├── ConditionBuilder.tsx   # 매수/매도 조건 시각 편집 + AI Text-to-Rule
│   │   └── BacktestResultPanel.tsx # 백테스트 결과 통계 패널
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
│   └── api.ts                   # API 클라이언트 (+ ordersApi 주문)
│
├── types/
│   ├── portfolio.ts             # Portfolio, Position 타입
│   ├── agent.ts                 # Agent, AgentLog, MarketSignal, ...
│   ├── trade.ts                 # Trade, TradeListResponse 타입
│   ├── wallet.ts                # WalletBalance, WalletAsset 타입
│   └── system_trading.ts        # 시스템 트레이딩 타입 (조건식, 백테스트, 템플릿)
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

### 내 지갑 (`/wallet`)
- Binance 계좌 잔액 조회 (페이퍼/실거래 모드 모두 지원)
- 상단 4개 요약 카드: 총 자산(USD/KRW), 현금(USDT), 코인 가치, 보유 종류 수
- 코인별 자산 테이블: 수량, 현재가, 평가금액(USD+KRW), 비중(%), 24h 변동률
- 비중 프로그레스 바 시각화
- 소액 자산 숨기기 토글 ($0.01 미만)
- SWR 30초 자동 갱신 + 수동 새로고침 버튼
- PAPER / LIVE 모드 배지 표시

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
| `ordersApi` | `market/limit/orderbook/sellAllFree/getOpen/cancel/...` | REST 주문·미체결·취소 |
| `tradeApi` | `getTrades()` | DB 거래 내역 |
| `tradeApi` | `closeAllPositions()` | 전체 청산 |
| `agentApi` | `getAgents()` | 에이전트 상태 |
| `agentApi` | `getAgentLogs()` | 로그 조회 |
| `agentApi` | `startAgent(type)` | 에이전트 시작 |
| `agentApi` | `stopAgent(type)` | 에이전트 중지 |
| `settingsApi` | `getSettings()` | 설정 조회 |
| `settingsApi` | `updateRiskSettings()` | 리스크 설정 |
| `settingsApi` | `updateStrategySettings()` | 전략 설정 |
| `walletApi` | `getBalance()` | 지갑 잔액 조회 |
| `systemTradingApi` | `listConditions()` | 조건식 목록 |
| `systemTradingApi` | `createCondition(data)` | 조건식 생성 |
| `systemTradingApi` | `updateCondition(id, data)` | 조건식 수정 |
| `systemTradingApi` | `deleteCondition(id)` | 조건식 삭제 |
| `systemTradingApi` | `textToRule(text, side)` | 자연어 → 조건 변환 |
| `systemTradingApi` | `getTemplates()` | 전략 템플릿 목록 |
| `systemTradingApi` | `backtest(params)` | 백테스트 실행 |
| `systemTradingApi` | `checkNow(params)` | 현재 조건 체크 |

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

### 시스템 트레이딩 (`/system-trading`)
- TradingView 스타일 캔들 차트 + Buy(▲)/Sell(▼) 마커
- 조건식 CRUD (좌 목록 + 우 편집 패널)
- 매수/매도 조건 시각 편집 (드롭다운 선택 + 파라미터 입력)
- AI Text-to-Rule: 자연어 → 조건 변환 (패턴 매칭)
- 전략 템플릿 5종 (RSI/MACD/볼린저/이평선/스토캐스틱)
- 백테스트 실행 → 승률/평균수익/MDD 통계 표시
- "지금 체크" → 현재 시장 데이터로 조건 즉시 평가

*최종 업데이트: 2026-03-09*  
*버전: 1.2.0*
