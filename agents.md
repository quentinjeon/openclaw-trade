# OpenClaw 에이전트 시스템 명세

> **규칙**: 이 파일은 시스템의 모든 에이전트 구조를 정의합니다.  
> 에이전트 추가/변경 시 반드시 이 파일과 해당 폴더의 `agents.md`를 업데이트하세요.

## 시스템 개요

OpenClaw 암호화폐 자동매매 시스템은 **5개의 전문 에이전트**가 파이프라인 방식으로 협력하여 자율적으로 매매를 수행합니다.

```
[MarketAnalyzerAgent]
        ↓ MarketSignal
[StrategyAgent]
        ↓ TradingSignal  
[RiskManagerAgent]
        ↓ ApprovedOrder
[ExecutionAgent]
        ↓ TradeResult
[PortfolioAgent]
```

---

## 에이전트 목록

### 1. MarketAnalyzerAgent
- **위치**: `backend/agents/market_analyzer.py`
- **역할**: 시장 데이터 수집 및 기술적 분석
- **실행 주기**: 1분마다
- **입력**: 거래소 OHLCV 데이터, 오더북
- **출력**: `MarketSignal` (BULLISH / BEARISH / NEUTRAL)
- **분석 지표**:
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - 볼린저 밴드 (Bollinger Bands)
  - 이동평균선 (MA 20, 50, 200)
  - 거래량 분석

### 2. StrategyAgent
- **위치**: `backend/agents/strategy_agent.py`
- **역할**: 매매 전략 실행 및 신호 생성 (기본 활성: **Larry Williams %R** `larry_williams`, 설정에서 RSI/MACD/볼린저 병행 가능)
- **실행 주기**: MarketSignal 수신 시
- **입력**: `MarketSignal`, 설정된 전략 파라미터
- **출력**: `TradingSignal` (BUY / SELL / HOLD)
- **지원 전략**:
  - RSI 역추세 전략
  - MACD 크로스오버 전략
  - 볼린저 밴드 돌파 전략
  - 복합 전략 (다중 지표 합산)

### 3. RiskManagerAgent
- **위치**: `backend/agents/risk_manager.py`
- **역할**: 리스크 평가 및 포지션 크기 결정
- **실행 주기**: TradingSignal 수신 시
- **입력**: `TradingSignal`, 계좌 잔고, 현재 포지션
- **출력**: `ApprovedOrder` (승인) 또는 `RejectedSignal` (거부)
- **리스크 체크**:
  - 최대 포지션 크기 (계좌의 %)
  - 최대 동시 포지션 수
  - 일일 손실 한도
  - 연속 손실 횟수 제한

### 4. ExecutionAgent
- **위치**: `backend/agents/execution_agent.py`
- **역할**: 거래소에 실제 주문 실행
- **실행 주기**: ApprovedOrder 수신 시
- **입력**: `ApprovedOrder`
- **출력**: `TradeResult`
- **기능**:
  - 시장가/지정가 주문
  - 손절/익절 주문 자동 설정
  - 페이퍼트레이딩 모드 지원
  - 주문 체결 확인 및 재시도

### 5. PortfolioAgent
- **위치**: `backend/agents/portfolio_agent.py`
- **역할**: 포트폴리오 성과 추적 및 리포트
- **실행 주기**: 1분마다 + TradeResult 수신 시
- **입력**: `TradeResult`, 계좌 잔고
- **출력**: `PortfolioSnapshot`
- **추적 지표**:
  - 총 자산 가치 (USD)
  - 보유 포지션 목록
  - 일일/총 손익 (PnL)
  - 승률 및 평균 수익률

---

## 에이전트 통신 프로토콜

### 신호 타입
```python
class MarketSignal(BaseModel):
    symbol: str           # BTC/USDT
    exchange: str         # binance
    direction: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float     # 0.0 ~ 1.0
    indicators: dict      # {"rsi": 35.2, "macd": 0.001, ...}
    timestamp: datetime

class TradingSignal(BaseModel):
    market_signal: MarketSignal
    action: Literal["BUY", "SELL", "HOLD"]
    strategy: str         # "rsi_reversal"
    reasoning: str        # 매매 근거 설명
    timestamp: datetime

class ApprovedOrder(BaseModel):
    trading_signal: TradingSignal
    symbol: str
    side: Literal["buy", "sell"]
    amount: float         # 수량
    price: Optional[float]  # None이면 시장가
    stop_loss: float
    take_profit: float
```

---

## 에이전트 상태 관리

| 상태 | 설명 |
|------|------|
| `IDLE` | 대기 중 |
| `RUNNING` | 실행 중 |
| `ANALYZING` | 분석 중 |
| `EXECUTING` | 주문 실행 중 |
| `ERROR` | 오류 발생 |
| `STOPPED` | 중지됨 |

---

## 폴더별 agents.md

| 폴더 | agents.md 위치 | 내용 |
|------|---------------|------|
| 루트 | `agents.md` | 전체 시스템 에이전트 개요 |
| backend | `backend/agents.md` | 백엔드 에이전트 상세 명세 |
| frontend | `frontend/agents.md` | 프론트엔드 컴포넌트 구조 명세 |

---

---

## 추가 기능 모듈

### 내 지갑 (Wallet)
- **백엔드**: `backend/routers/wallet.py` — `GET /api/wallet/balance`
- **프론트엔드**: `frontend/src/app/wallet/page.tsx`
- **역할**: Binance 계좌 잔액 조회 및 KRW 환산 표시
- **PRD**: `docs/prd/wallet.md`

---

*최종 업데이트: 2026-03-09*  
*버전: 1.1.0*
