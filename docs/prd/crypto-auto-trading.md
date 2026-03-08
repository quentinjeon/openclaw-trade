# PRD: 암호화폐 자동매매 시스템 (OpenClaw Trading System)

## 1. 제품 개요

### 1.1 목적
OpenClaw 멀티 에이전트 프레임워크를 활용하여 암호화폐 자동매매 시스템을 구축한다.
각 에이전트가 독립적인 역할(시장분석, 전략실행, 리스크관리, 포트폴리오관리)을 수행하며 협력하는 구조를 갖는다.

### 1.2 비전
- **자율적 판단**: AI 에이전트가 시장 데이터를 분석하고 독립적으로 매매 결정
- **리스크 최소화**: 다층 리스크 관리 에이전트가 손실을 자동 제한
- **투명한 운영**: 실시간 대시보드로 모든 에이전트 활동 모니터링
- **확장성**: 새로운 전략/거래소/코인을 쉽게 추가 가능

### 1.3 핵심 지표 (KPI)
- 월 수익률 목표: +5% ~ +15% (시장 상황에 따라 조정)
- 최대 드로다운: -10% 이내
- 에이전트 응답 시간: < 100ms
- 시스템 가동률: 99.9%

---

## 2. 사용자 스토리

### 2.1 트레이더 (운영자)
- **US-001**: 나는 트레이더로서 실시간 포트폴리오 현황을 대시보드에서 확인하고 싶다.
- **US-002**: 나는 트레이더로서 각 에이전트의 매매 결정 근거를 확인하고 싶다.
- **US-003**: 나는 트레이더로서 리스크 파라미터(손절가, 포지션 크기)를 설정하고 싶다.
- **US-004**: 나는 트레이더로서 원하는 거래소와 코인 페어를 자유롭게 추가하고 싶다.
- **US-005**: 나는 트레이더로서 백테스트로 전략 성능을 미리 확인하고 싶다.

### 2.2 시스템 관리자
- **US-006**: 나는 관리자로서 에이전트 상태를 실시간으로 모니터링하고 싶다.
- **US-007**: 나는 관리자로서 비상 시 모든 포지션을 즉시 청산할 수 있어야 한다.

---

## 3. 시스템 아키텍처

### 3.1 전체 구조
```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 14)                    │
│  Dashboard │ Portfolio │ Agents │ Settings │ Backtest        │
└─────────────────────┬───────────────────────────────────────┘
                      │ REST API / WebSocket
┌─────────────────────▼───────────────────────────────────────┐
│                    Backend (FastAPI)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              OpenClaw Agent Orchestrator              │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐  │    │
│  │  │  Market  │ │Strategy │ │  Risk   │ │Portfolio│  │    │
│  │  │ Analyzer │ │  Agent  │ │ Manager │ │  Agent │  │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬────┘ └───┬───┘  │    │
│  └───────┼────────────┼────────────┼───────────┼───────┘    │
│          │            │            │           │             │
│  ┌───────▼────────────▼────────────▼───────────▼───────┐    │
│  │              Exchange Connector (ccxt)                │    │
│  │        Binance │ Upbit │ Bybit │ OKX                 │    │
│  └───────────────────────────────────────────────────────┘    │
│  ┌───────────────────────────────────────────────────────┐    │
│  │              Database (SQLite / PostgreSQL)            │    │
│  └───────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 에이전트 역할

| 에이전트 | 역할 | 입력 | 출력 |
|---------|------|------|------|
| MarketAnalyzerAgent | 시장 데이터 수집 및 기술적 분석 | OHLCV, 오더북, 뉴스 | 시장 신호 (BULLISH/BEARISH/NEUTRAL) |
| StrategyAgent | 매매 전략 실행 | 시장 신호, 가격 데이터 | 매매 신호 (BUY/SELL/HOLD) |
| RiskManagerAgent | 리스크 평가 및 포지션 크기 결정 | 매매 신호, 계좌 잔고 | 승인/거부 + 포지션 크기 |
| ExecutionAgent | 실제 주문 실행 | 승인된 매매 신호 | 주문 결과 |
| PortfolioAgent | 포트폴리오 성과 추적 | 거래 기록 | 성과 리포트 |

---

## 4. 기능 명세

### 4.1 핵심 기능 (MVP)

#### F-001: 멀티 에이전트 매매 시스템
- **설명**: 5개 에이전트가 파이프라인으로 협력하는 자동매매
- **우선순위**: P0 (필수)
- **완료 조건**:
  - [ ] MarketAnalyzerAgent가 1분마다 시장 데이터를 수집/분석
  - [ ] StrategyAgent가 RSI, MACD, 볼린저 밴드 기반 신호 생성
  - [ ] RiskManagerAgent가 포지션 크기 자동 계산
  - [ ] ExecutionAgent가 실제/페이퍼 거래 실행
  - [ ] PortfolioAgent가 실시간 성과 추적

#### F-002: 실시간 대시보드
- **설명**: 포트폴리오 및 에이전트 활동 실시간 모니터링
- **우선순위**: P0 (필수)
- **완료 조건**:
  - [ ] 실시간 포트폴리오 가치 차트
  - [ ] 에이전트별 활동 로그 스트림
  - [ ] 보유 포지션 목록 및 손익
  - [ ] 거래 내역 테이블

#### F-003: 전략 설정
- **설명**: 다양한 매매 전략을 설정/활성화
- **우선순위**: P1 (중요)
- **완료 조건**:
  - [ ] RSI 전략 파라미터 설정 (기간, 과매수/과매도 기준)
  - [ ] MACD 전략 파라미터 설정
  - [ ] 볼린저 밴드 전략 파라미터 설정
  - [ ] 전략 ON/OFF 토글

#### F-004: 리스크 관리 설정
- **설명**: 리스크 파라미터 커스터마이징
- **우선순위**: P1 (중요)
- **완료 조건**:
  - [ ] 최대 포지션 크기 설정 (계좌의 %)
  - [ ] 손절가 자동 설정
  - [ ] 최대 동시 포지션 수 제한
  - [ ] 일일 최대 손실 한도 설정

#### F-005: 백테스트
- **설명**: 과거 데이터로 전략 성능 검증
- **우선순위**: P2 (향후)
- **완료 조건**:
  - [ ] 날짜 범위 설정
  - [ ] 전략별 성과 지표 (샤프 비율, MDD, 승률)
  - [ ] 가상 거래 내역 시각화

### 4.2 거래소 지원

| 거래소 | 현물 | 선물 | API 키 필요 |
|--------|------|------|------------|
| Binance | ✅ | ✅ | ✅ |
| Upbit | ✅ | ❌ | ✅ |
| Bybit | ✅ | ✅ | ✅ |
| OKX | ✅ | ✅ | ✅ |

---

## 5. 기술 스택

### 5.1 백엔드
- **프레임워크**: FastAPI 0.110+
- **언어**: Python 3.11+
- **에이전트 프레임워크**: OpenClaw (커스텀 멀티에이전트)
- **거래소 연동**: ccxt 4.x
- **데이터 분석**: pandas, numpy, ta-lib
- **스케줄러**: APScheduler
- **DB**: SQLite (개발) / PostgreSQL (운영)
- **캐시**: Redis
- **실시간**: WebSocket (FastAPI native)

### 5.2 프론트엔드
- **프레임워크**: Next.js 14 (App Router)
- **언어**: TypeScript
- **스타일링**: Tailwind CSS + shadcn/ui
- **차트**: Recharts + TradingView Lightweight Charts
- **상태관리**: Zustand
- **실시간**: WebSocket + SWR
- **아이콘**: Lucide React

### 5.3 인프라
- **컨테이너**: Docker + Docker Compose
- **환경설정**: .env 파일 기반

---

## 6. 데이터 모델

### 6.1 Trade (거래)
```sql
CREATE TABLE trades (
  id          TEXT PRIMARY KEY,
  symbol      TEXT NOT NULL,          -- BTC/USDT
  exchange    TEXT NOT NULL,          -- binance
  side        TEXT NOT NULL,          -- buy | sell
  type        TEXT NOT NULL,          -- market | limit
  amount      REAL NOT NULL,
  price       REAL NOT NULL,
  cost        REAL NOT NULL,
  fee         REAL,
  status      TEXT NOT NULL,          -- open | closed | cancelled
  agent_id    TEXT,                   -- 실행한 에이전트 ID
  strategy    TEXT,                   -- 사용된 전략
  signal_data TEXT,                   -- JSON: 매매 신호 데이터
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 AgentLog (에이전트 로그)
```sql
CREATE TABLE agent_logs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id    TEXT NOT NULL,
  agent_type  TEXT NOT NULL,          -- market_analyzer | strategy | risk | execution | portfolio
  level       TEXT NOT NULL,          -- INFO | WARNING | ERROR | DECISION
  message     TEXT NOT NULL,
  data        TEXT,                   -- JSON 추가 데이터
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 6.3 Portfolio (포트폴리오 스냅샷)
```sql
CREATE TABLE portfolio_snapshots (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  total_value_usd REAL NOT NULL,
  cash_usd        REAL NOT NULL,
  positions       TEXT NOT NULL,      -- JSON
  pnl_daily       REAL,
  pnl_total       REAL,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. API 명세

### 7.1 REST API

| Method | Path | 설명 |
|--------|------|------|
| GET | /api/portfolio | 현재 포트폴리오 조회 |
| GET | /api/trades | 거래 내역 조회 |
| POST | /api/trades/close-all | 전체 포지션 청산 |
| GET | /api/agents | 에이전트 상태 조회 |
| POST | /api/agents/{id}/start | 에이전트 시작 |
| POST | /api/agents/{id}/stop | 에이전트 중지 |
| GET | /api/strategies | 전략 목록 조회 |
| PUT | /api/strategies/{id} | 전략 설정 변경 |
| GET | /api/settings | 전체 설정 조회 |
| PUT | /api/settings | 설정 저장 |
| POST | /api/backtest | 백테스트 실행 |

### 7.2 WebSocket

| 채널 | 설명 |
|------|------|
| /ws/portfolio | 실시간 포트폴리오 업데이트 |
| /ws/agents | 실시간 에이전트 로그 스트림 |
| /ws/trades | 실시간 거래 체결 알림 |
| /ws/market | 실시간 시세 데이터 |

---

## 8. 개발 로드맵

### Phase 1: MVP (현재)
- [x] PRD 작성
- [ ] 프로젝트 기본 구조 설정
- [ ] 에이전트 시스템 구현
- [ ] 거래소 연동 (Binance 페이퍼트레이딩)
- [ ] 기본 전략 구현 (RSI, MACD)
- [ ] 기본 대시보드 구현

### Phase 2: 확장
- [ ] 다중 거래소 지원
- [ ] 고급 전략 추가 (ML 기반)
- [ ] 백테스트 시스템
- [ ] 알림 시스템 (Telegram, 이메일)

### Phase 3: 최적화
- [ ] 전략 자동 최적화
- [ ] 멀티 심볼 동시 거래
- [ ] 성과 분석 고도화

---

## 9. 리스크 및 주의사항

> ⚠️ **중요**: 이 시스템은 실제 자금을 자동으로 거래합니다. 반드시 페이퍼트레이딩(모의거래)으로 충분히 테스트한 후 실거래에 적용하세요.

- 암호화폐 투자는 원금 손실 위험이 있습니다
- API 키는 반드시 `.env` 파일에 보관하고 git에 커밋하지 마세요
- 리스크 파라미터를 보수적으로 시작하세요 (최대 포지션 5% 권장)

---

*최초 작성: 2026-03-08*  
*작성자: OpenClaw System*  
*버전: 1.0.0*
