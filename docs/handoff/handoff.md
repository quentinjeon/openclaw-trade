# OpenClaw 인수인계 문서 (Handoff)

> **⚠️ 에이전트/터미널을 새로 시작할 때 반드시 이 파일을 가장 먼저 읽으세요.**  
> 최신 개발 현황, 실행 방법, 미완성 항목이 모두 여기 기록됩니다.

---

## 🕐 최신 업데이트

| 항목 | 내용 |
|------|------|
| **최종 업데이트** | 2026-03-18 (KST) |
| **버전** | v0.5.7 |
| **백엔드 포트** | `8002` |
| **프론트엔드 포트** | `3001` |
| **DB** | SQLite (`DATABASE_URL`, 기본 `backend/openclaw.db` — 실행 cwd 기준) |
| **거래소** | Binance 현물 (기본 **실거래** · `PAPER_TRADING=true` 시 시뮬) |

---

## 🚀 현재 실행 방법

### 백엔드 시작 (FastAPI)
```bash
cd /Users/junyongsub/openclaw/backend
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### 프론트엔드 시작 (Next.js)
```bash
cd /Users/junyongsub/openclaw/frontend
npm run dev -- --port 3001
```

### 접속 URL
- 프론트엔드: http://localhost:3001
- 백엔드 API: http://localhost:8002
- API 문서 (Swagger): http://localhost:8002/docs

---

## 🕐 최신 업데이트 (v0.5.7 — 2026-03-18)

### 매수 규모 = 실제 쿼트 free + 최소 명목가
- **RiskManager** 실거래 매수 시 거래소 **`fetch_balance` → 심볼 쿼트(USDT 등) free** 로 리스크·수량 계산 (`set_connector`)
- **가용** = free × (1 − `CASH_FEE_RESERVE_PCT`) — 수수료·슬리피지 여유
- **최소 명목가** 미만이면 자동 상향(가용 내) 또는 **거부** (명목 부족으로 주문 실패 방지)
- **수량 step** (`amount_to_precision`) 반영 후에도 명목·가용 재검증
- 전략 파이프라인·Pick 자동매수·보유 청산 전 매수 동일 경로 (`evaluate_signal`)

---

## 🕐 이전 업데이트 (v0.5.6 — 2026-03-18)

### UI 시간대 (한국시간 KST)
- `formatDateTime` / `formatDateTimeFull`: API **타임존 없는 UTC 문자열**을 UTC로 파싱 후 `Asia/Seoul` 표시 (`parseApiDateTime`)
- 시장 **캔들 차트** 축·크로스헤어: KST 라벨 (`CandleChart` localization)
- 파이프라인 활성 만료·매매점수 갱신·지갑·대기 주문: 한국시간 문구 정리

---

## 🕐 이전 업데이트 (v0.5.5 — 2026-03-18)

### 기동 부트스트랩 (`STARTUP_BOOTSTRAP_TRADING`, 기본 true)
- 서버 시작 시 **TRX free 잔고 전량 매도**(TRX/USDT, 호가 공격 지정가) → 없으면 스킵
- **전략·리스크 에이전트** 포함 5종 에이전트 주기 가동 (이전에는 시장·체결·포트만 자동 시작)
- 재기동할 때마다 TRX를 다시 팔 수 있으므로, TRX를 보유할 계획이면 `.env` 에 `STARTUP_BOOTSTRAP_TRADING=false`
- 수동: `POST /api/agents/bootstrap-auto-trading` · 프론트 `agentApi.bootstrapAutoTrading()`

### REST 주문 API (`/api/orders/*`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/constraints/{symbol}` | 최소 수량·명목가 |
| POST | `/market` | 시장가 매수/매도 |
| POST | `/limit` | 지정가 (`wait_for_fill` 선택) |
| POST | `/orderbook` | 호가 최유리 지정가 |
| POST | `/sell-all-free` | 베이스 코인 free 전량 매도 |
| GET | `/open` | 미체결 목록 |
| GET | `/status` | 주문 단건 |
| DELETE | `/cancel` | 미체결 취소 |
| POST | `/cancel-all` | 미체결 전부 취소 |
| GET | `/exchange-trades` | 거래소 최근 체결 |

프론트: `ordersApi` (`frontend/src/services/api.ts`)

### 호가 지정가 체결 (기본)
- **`ORDER_EXECUTION_MODE=orderbook`**: 매수는 **최우선 매수호가(bid)**, 매도는 **최우선 매도호가(ask)** 에 지정가 → 시장가보다 유리한 쪽 대기 (`ORDER_FILL_MAX_WAIT_SEC` 내 미체결 시 취소)
- 손절·익절·긴급 전체청산: 지정가이되 **매수호가 쪽 매도(aggressive)** 로 빠른 체결. `market`으로 바꾸면 전부 시장가.

### 실거래 기본 + 대시보드 실데이터
- **기본 `PAPER_TRADING=false`**, `BINANCE_TESTNET=false` — 현물 메인넷 + API 키로 체결·잔고 조회
- **포트폴리오 에이전트**: 실거래 시 주기적으로 **거래소 잔고 동기화** → 총자산·현금(스테이블)·보유 코인 = 실계좌. 봇 진입 포지션은 진입가·SL/TP 병합(`managed_by_bot`)
- **매매 점수 루프**: 감시 심볼 + **실계좌 보유 코인** USDT 마켓 자동 포함
- 대시보드: **실거래 배너**(현금·총자산), 사이드바 **LIVE** 배지, 보유 테이블 **거래소 기준** 문구

### DB·API 정합성 (v0.5.4)
- **체결/실패 시 `trades` 테이블 INSERT** (`services/trade_persistence.py`, `TradeResult.realized_pnl`로 매도 실현손익 기록)
- **`GET /api/trades/`** `total` = 필터 적용 후 전체 건수 (페이지네이션 정확)
- **`portfolio_snapshots`**: `winning_trades`, `losing_trades`, `initial_balance`, `total_return_pct` 컬럼 + 기존 SQLite `init_db` 시 `ALTER` 마이그레이션
- **시스템 트레이딩 API** 조건식 응답에 **`backtest_ran_at`** 포함 · 프론트 타입 동기화

---

## 🕐 이전 업데이트 (v0.5.3 — 2026-03-18)

### 매수·매도·보유 점수 & 자금 비중 (대시보드)
- `services/score_trading.py` — 매수/매도/보유 점수 0~100 (Williams %R, RSI, MACD, SMA20, 시장 방향)
- 전략 에이전트가 점수·Larry 합성으로 BUY/SELL/HOLD, **매수 시 `_score_alloc_mult`** 로 최대 포지션 대비 투입 비중 조절
- `GET /api/trading-scores/` + 약 50초마다 감시 심볼·보유 심볼 점수 갱신
- 대시보드 **매수·매도·보유 점수** 패널: 심볼별 3바 + 권장 투자/현금 비중 요약

### 보유 코인 자동 매도(청산)
- **ExecutionAgent** `run_cycle`: 손절/익절 후, 약 **60초마다** `active_positions` 각 심볼에 대해 **Larry Williams %R** 1h 봉으로 매도 신호 스캔 → `RiskManager` → **매도는 수동 승인 없이 즉시 시장가 체결**
- **RiskManager**: 매도 시 주문 수량 = **추적 중인 포지션 전량**; 일일 손실 한도·최소 잔고는 **매수에만** 적용
- **StrategyAgent** 복합 집계: SELL은 시장 BULLISH여도 통과 가능(청산 목적)

### 백테스트 단기 파이프라인 (대시보드)
- `GET/POST /api/pipeline-opportunities/*` — 5분봉 유사 신호 통계 + 활성화 시 해당 심볼 매수 자동체결
- `PipelineOpportunityCards` — 조건 불만족 시 카드 미표시

### 종목 스캐너·자동매수
- `docs/prd/pick-scanner.md` — 백테스트 점수화·자동매수 PRD 요약
- `backend/services/pick_scanner.py` — 점수 산식 + 심볼별 백테스트
- `backend/services/pick_scanner_config.py` — JSON 설정 (`backend/data/pick_scanner_config.json`)
- `backend/services/pick_auto_buy.py` — 스캔 루프·RiskManager 매수 연동
- `backend/routers/picks.py` — `/api/picks/*`
- `main.py` — 스캔 간격마다 자동매수 백그라운드 태스크 (설정 ON 시)
- `frontend/src/app/picks/page.tsx` — 종목 스캔 UI
- 사이드바 **종목 스캔** 메뉴

---

## 🕐 이전 업데이트 (v0.5.0 — 2026-03-09)

### 시스템 트레이딩 기능 추가

- `docs/prd/system-trading.md` — 30년 트레이딩 도구 관점 상세 PRD
- `backend/models/system_condition.py` — 조건식 DB 모델
- `backend/services/condition_evaluator.py` — 조건 평가 엔진 (ta 라이브러리 활용)
- `backend/services/backtester.py` — 백테스트 엔진 (수수료 0.1% 반영)
- `backend/services/rule_parser.py` — Text-to-Rule 파서 (한국어 패턴 + 영어)
- `backend/routers/system_trading.py` — REST API 8개 엔드포인트
- `frontend/src/types/system_trading.ts` — 타입 정의 + 지표/연산자 옵션
- `frontend/src/components/market/CandleChart.tsx` — Buy/Sell 마커 지원 추가
- `frontend/src/components/system-trading/ConditionBuilder.tsx` — 조건 편집 패널
- `frontend/src/components/system-trading/BacktestResultPanel.tsx` — 결과 패널
- `frontend/src/app/system-trading/page.tsx` — 메인 페이지 (차트+편집 2패널)
- `Sidebar.tsx` — "시스템 트레이딩" 메뉴 추가 (BotMessageSquare 아이콘)

---

## 🕐 이전 업데이트 (v0.4.0 — 2026-03-09)

### 내 지갑 페이지 추가
- `backend/routers/wallet.py` — `GET /api/wallet/balance` (코인별 잔액 + USD/KRW 환산)
- `frontend/src/app/wallet/page.tsx` — 내 지갑 페이지 (SWR 30초 갱신)
- `frontend/src/components/wallet/WalletSummaryCards.tsx` — 상단 요약 카드
- `frontend/src/components/wallet/AssetTable.tsx` — 코인 자산 테이블 + 비중 프로그레스 바
- `frontend/src/types/wallet.ts` — 타입 정의
- `Sidebar.tsx` — "내 지갑" 메뉴 추가 (`Wallet` 아이콘)
- `docs/prd/wallet.md` — PRD 문서
- `.cursor/rules/wallet.mdc` — MDC 규칙

---

## ✅ 개발 완료 목록

### 백엔드

#### 코어
- [x] `backend/core/config.py` — 환경변수 설정 (pydantic-settings v2, JSON 배열 파싱)
- [x] `backend/core/database.py` — SQLAlchemy async SQLite 연결
- [x] `backend/core/websocket.py` — WebSocket 채널 관리 (portfolio/agents/trades/market)

#### 에이전트 파이프라인 (5개)
- [x] `backend/agents/base_agent.py` — 추상 기본 에이전트 클래스
- [x] `backend/agents/market_analyzer.py` — 시장 분석 (RSI/MACD/BB/MA, 1분 주기)
- [x] `backend/agents/strategy_agent.py` — 전략 실행 (RSI역추세/MACD크로스/볼린저)
- [x] `backend/agents/risk_manager.py` — 리스크 평가 및 포지션 크기 결정
- [x] `backend/agents/execution_agent.py` — 주문 실행 + 손절/익절 모니터링
- [x] `backend/agents/portfolio_agent.py` — 포트폴리오 추적 및 리포트

#### 전략
- [x] `backend/strategies/rsi_strategy.py` — RSI 역추세 전략
- [x] `backend/strategies/macd_strategy.py` — MACD 크로스오버 전략
- [x] `backend/strategies/bollinger_strategy.py` — 볼린저밴드 돌파 전략

#### 거래소 연결
- [x] `backend/exchange/connector.py` — ccxt 기반 Binance 연결, 페이퍼트레이딩 지원

#### DB 모델
- [x] `backend/models/trade.py` — 거래 내역 테이블
- [x] `backend/models/agent_log.py` — 에이전트 로그 테이블
- [x] `backend/models/portfolio.py` — 포트폴리오 스냅샷 테이블

#### 시스템 트레이딩
- [x] `backend/models/system_condition.py` — 조건식 DB 모델
- [x] `backend/services/condition_evaluator.py` — 조건 평가 엔진 (20+ 지표 지원)
- [x] `backend/services/backtester.py` — 백테스트 엔진 (수수료 포함, MDD 계산)
- [x] `backend/services/rule_parser.py` — 자연어 → 조건 파서 (패턴 매칭 30+ 패턴)

#### API 라우터
- [x] `backend/routers/portfolio.py` — `GET /api/portfolio`
- [x] `backend/routers/trades.py` — `GET /api/trades`
- [x] `backend/routers/agents.py` — `GET/POST /api/agents` (시작/중지)
- [x] `backend/routers/settings.py` — `GET/PUT /api/settings`
- [x] `backend/routers/wallet.py` — `GET /api/wallet/balance` (지갑 잔액)
- [x] `backend/routers/system_trading.py` — 시스템 트레이딩 API
  - [x] `GET/POST/PUT/DELETE /api/system/conditions` — 조건식 CRUD
  - [x] `POST /api/system/text-to-rule` — 자연어 → 조건 변환
  - [x] `GET /api/system/templates` — 전략 템플릿 5종
  - [x] `POST /api/system/backtest` — 백테스트 실행
  - [x] `POST /api/system/check-now` — 현재 조건 즉시 체크
- [x] `backend/routers/market.py` — 시황 분석 API (아래 상세)
  - [x] `GET /api/market/overview` — BTC/ETH 요약
  - [x] `GET /api/market/ticker/{symbol}` — 개별 시세
  - [x] `GET /api/market/candles/{symbol}?timeframe=1h` — OHLCV 캔들
  - [x] `GET /api/market/watchlist` — 다종목 워치리스트 (`core/symbol_lists.py`)
  - [x] `GET /api/market/fx` — USD/KRW 환율 (5분 캐시, frankfurter.app)

---

### 프론트엔드

#### 페이지 (8개)
- [x] `/` — 메인 대시보드 (포트폴리오 요약, 에이전트 상태, 실시간 로그)
- [x] `/market` — 시황 분석 (TradingView 캔들차트 고도화 - 3패널 레이아웃)
- [x] `/system-trading` — 시스템 트레이딩 (조건식 편집 + 백테스트 + Buy/Sell 차트 마커)
- [x] `/portfolio` — 포트폴리오 상세
- [x] `/wallet` — 내 지갑 (Binance 계좌 잔액, KRW 환산, 비중 차트)
- [x] `/agents` — 에이전트 모니터링 + 로그
- [x] `/trades` — 거래 내역
- [x] `/settings` — 리스크/전략 설정

#### 시황 분석 페이지 (`/market`) 기능
- [x] TradingView Lightweight Charts 캔들스틱 (상승=파랑, 하락=빨강, 한국식)
- [x] MA20(노랑)/MA50(주황)/MA200(보라) 오버레이
- [x] 볼린저밴드 상/하단 (회색 점선)
- [x] 거래량 서브 차트
- [x] 타임프레임 선택 (1분/5분/15분/1시간/4시간/일)
- [x] MA·BB 토글 버튼
- [x] 우측 워치리스트 (BTC·ETH·L1/L2·DeFi 등 30+ 심볼)
- [x] USD 가격 + KRW 환산가 동시 표시
- [x] 환율 표시 (`$1 = ₩1,485`)
- [x] 기술 지표 패널 (RSI/MACD/BB/MA 크로스 분석)
- [x] OpenClaw 에이전트 매매 신호 표시
- [x] 30초 자동 새로고침 + 수동 버튼

#### 공통 컴포넌트
- [x] `CandleChart.tsx` — lightweight-charts 래퍼 (dispose 버그 수정 완료)
- [x] `Sidebar.tsx` — 6개 메뉴 네비게이션
- [x] `PortfolioSummary.tsx` — 4개 메트릭 카드
- [x] `PositionTable.tsx` — 보유 포지션 테이블
- [x] `AgentStatusPanel.tsx` — 에이전트 상태 패널
- [x] `AgentLogStream.tsx` — 실시간 로그 터미널
- [x] `TradeHistoryTable.tsx` — 거래 내역 테이블

#### 유틸
- [x] `lib/utils.ts` — `formatUSD`, `formatKRW`, `formatPercent`, `nowKST`, `formatDateTime`
- [x] `services/api.ts` — `portfolioApi`, `tradeApi`, `agentApi`, `settingsApi`, `marketApi`
- [x] `hooks/useWebSocket.ts` — WebSocket 커스텀 훅
- [x] `stores/portfolioStore.ts`, `agentStore.ts` — Zustand 스토어

---

## ❌ 미개발 / TODO 목록

### 높은 우선순위
- [ ] **실거래소 API 키 연결** — `.env`에 `BINANCE_API_KEY`, `BINANCE_SECRET_KEY` 입력 필요  
  현재: 페이퍼트레이딩 모드로만 동작
- [ ] **WebSocket 실시간 업데이트** — 백엔드 ws 채널 구현됐으나 프론트엔드 연동 확인 필요  
  `ws://localhost:8002/ws/portfolio` 등 연결 테스트 필요
- [ ] **에이전트 실제 자동 시작** — 현재 수동으로 `/api/agents/{type}/start` 호출 필요  
  시스템 시작 시 에이전트 자동 실행 옵션 추가 필요

### 중간 우선순위
- [ ] **차트 KRW 가격축** — 캔들 차트 오른쪽 가격 축을 USDT→KRW로 전환하는 토글 버튼
- [ ] **주문창 UI** — 수동 매수/매도 주문 폼 (현재 에이전트 자동매매만 가능)
- [ ] **알림 시스템** — 매매 체결 시 브라우저 알림 또는 텔레그램 알림
- [ ] **백테스팅 모드** — 과거 데이터로 전략 성능 검증 기능
- [ ] **성과 차트** — 포트폴리오 가치 변화 시계열 차트 (`/portfolio` 페이지)
- [ ] **다크/라이트 테마** — 현재 다크 테마 고정, 라이트 모드 옵션 없음

### 낮은 우선순위
- [ ] **Docker 재구성** — 이전 Docker 빌드 npm 네트워크 오류로 중단, 재시도 필요
- [ ] **다중 거래소 지원** — 현재 Binance만, Upbit/Bybit 추가 필요
- [ ] **모바일 반응형** — 현재 데스크탑 전용 (min-width 제약 없음이나 최적화 안됨)
- [ ] **에이전트 파라미터 실시간 조정** — 설정 변경 후 에이전트 재시작 없이 반영
- [ ] **DB 마이그레이션 관리** — Alembic 설정됐으나 migration 파일 없음
- [ ] **유닛 테스트** — 전략/에이전트/API 테스트 코드 없음

---

## 🏗️ 시스템 구조 요약

```
[Binance ccxt]
     ↓
[MarketAnalyzerAgent] → RSI/MACD/BB 분석
     ↓ MarketSignal (BULLISH/BEARISH/NEUTRAL)
[StrategyAgent] → 전략 합산 (RSI/MACD/BB)
     ↓ TradingSignal (BUY/SELL/HOLD)
[RiskManagerAgent] → 포지션 크기 결정
     ↓ ApprovedOrder
[ExecutionAgent] → Binance 주문 실행 (페이퍼)
     ↓ TradeResult
[PortfolioAgent] → 성과 추적 → WebSocket → 프론트엔드
```

---

## 📁 핵심 파일 위치

| 역할 | 파일 경로 |
|------|----------|
| 백엔드 진입점 | `backend/main.py` |
| 환경변수 | `backend/.env` |
| 프론트엔드 환경변수 | `frontend/.env.local` |
| DB 파일 | `DATABASE_URL` (기본 `./openclaw.db`, 백엔드 cwd 기준) · 스키마 규칙 `.cursor/rules/db.mdc` |
| 시황 분석 라우터 | `backend/routers/market.py` |
| 지갑 라우터 | `backend/routers/wallet.py` |
| 시황 분석 페이지 | `frontend/src/app/market/page.tsx` |
| 내 지갑 페이지 | `frontend/src/app/wallet/page.tsx` |
| 캔들 차트 컴포넌트 | `frontend/src/components/market/CandleChart.tsx` |
| API 클라이언트 | `frontend/src/services/api.ts` |
| 공통 유틸 | `frontend/src/lib/utils.ts` |
| PRD 문서 | `docs/prd/` |

---

## ⚙️ 환경변수 핵심 항목

```env
# backend/.env
BINANCE_API_KEY=     ← 실거래 시 필수
BINANCE_SECRET_KEY=  ← 실거래 시 필수
PAPER_TRADING=false  ← 기본 실거래 (true 시 시뮬)
CORS_ORIGINS=["http://localhost:3001"]
DEFAULT_SYMBOLS=["BTC/USDT","ETH/USDT"]

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8002
NEXT_PUBLIC_WS_URL=ws://localhost:8002
```

---

## 🐛 알려진 버그 / 주의사항

| 버그 | 상태 | 설명 |
|------|------|------|
| CandleChart "Object is disposed" | ✅ 수정 완료 | useEffect cleanup 순서 문제, ref 제거로 해결 |
| CORS_ORIGINS 파싱 오류 | ✅ 수정 완료 | JSON 배열 형식으로 .env 저장 필요 |
| `formatDateTime` Invalid time value | ✅ 수정 완료 | null/undefined 입력 처리 추가 |
| Docker npm 네트워크 오류 | ⏳ 미해결 | 로컬 실행으로 우회 중 |
| WebSocket 연결 간헐적 끊김 | ⏳ 미확인 | 재연결 로직 있으나 테스트 필요 |

---

## 📖 관련 문서

- `docs/prd/crypto-auto-trading.md` — 전체 시스템 PRD
- `docs/prd/binance-research-trading.md` — 바이낸스 5레이어 연구 PRD
- `docs/prd/pick-scanner.md` — 종목 스캐너·자동매수
- `docs/prd/market-analysis-enhanced.md` — 시황분석 고도화 PRD
- `agents.md` (루트) — 에이전트 시스템 전체 명세
- `backend/agents.md` — 백엔드 에이전트 상세 명세
- `frontend/agents.md` — 프론트엔드 컴포넌트 명세

---

*이 파일은 개발 세션 종료 시마다 업데이트합니다.*  
*새 에이전트/터미널 시작 시 반드시 이 파일을 먼저 읽고 현황을 파악하세요.*
