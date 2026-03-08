# 백엔드 에이전트 상세 명세

> **규칙**: 에이전트 코드 변경 시 이 파일을 반드시 업데이트하세요.

## 에이전트 파이프라인

```
[MarketAnalyzerAgent]
  - 파일: agents/market_analyzer.py
  - 주기: 60초
  - 출력: MarketSignal
        ↓ on_signal 콜백
[StrategyAgent]
  - 파일: agents/strategy_agent.py
  - 주기: MarketSignal 수신 시 즉시
  - 출력: TradingSignal
        ↓ on_signal 콜백
[RiskManagerAgent]
  - 파일: agents/risk_manager.py
  - 주기: TradingSignal 수신 시 즉시
  - 출력: ApprovedOrder 또는 RejectedSignal
        ↓ on_approve 콜백
[ExecutionAgent]
  - 파일: agents/execution_agent.py
  - 주기: ApprovedOrder 수신 시 즉시 + 10초마다 손절/익절 체크
  - 출력: TradeResult
        ↓ on_trade_result 콜백
[PortfolioAgent]
  - 파일: agents/portfolio_agent.py
  - 주기: 60초 + TradeResult 수신 시
  - 출력: PortfolioState → WebSocket
```

---

## 에이전트 상세

### BaseAgent (`agents/base_agent.py`)

**추상 클래스 - 모든 에이전트의 기본**

| 속성/메서드 | 설명 |
|------------|------|
| `agent_id` | 고유 에이전트 ID (자동 생성) |
| `agent_type` | 에이전트 유형 (클래스에서 정의) |
| `status` | `AgentStatus` 열거형 |
| `run_cycle()` | 추상 메서드 - 반드시 구현 |
| `start(interval)` | 백그라운드 루프 시작 |
| `stop()` | 에이전트 중지 |
| `get_status()` | 상태 딕셔너리 반환 |
| `set_log_callback()` | DB 로그 콜백 등록 |

**에이전트 상태 (`AgentStatus`)**:
- `IDLE`: 대기 중
- `RUNNING`: 실행 중
- `ANALYZING`: 분석 중
- `EXECUTING`: 주문 실행 중
- `ERROR`: 오류 발생
- `STOPPED`: 중지됨

---

### MarketAnalyzerAgent (`agents/market_analyzer.py`)

**역할**: 시장 데이터 수집 및 기술적 분석

**생성자 파라미터**:
```python
MarketAnalyzerAgent(
    exchange: ExchangeConnector,  # 거래소 연결 객체
    symbols: List[str],           # 분석할 심볼 목록
    on_signal: Callable,          # MarketSignal 수신 콜백
)
```

**출력 (`MarketSignal`)**:
```python
@dataclass
class MarketSignal:
    symbol: str          # "BTC/USDT"
    exchange: str        # "binance"
    direction: str       # BULLISH | BEARISH | NEUTRAL
    confidence: float    # 0.0 ~ 1.0
    indicators: dict     # RSI, MACD, BB 값
    price: float
    volume_24h: float
    timestamp: datetime
```

**계산 지표**:
- RSI (14기간)
- MACD (12, 26, 9)
- 볼린저 밴드 (20기간, 2σ)
- MA (20, 50, 200)
- 거래량 비율

**방향성 판단 로직**:
- 4개 조건 중 60% 이상 동의 → BULLISH / BEARISH
- 나머지 → NEUTRAL

---

### StrategyAgent (`agents/strategy_agent.py`)

**역할**: 매매 전략 실행 및 신호 생성

**생성자 파라미터**:
```python
StrategyAgent(
    exchange: ExchangeConnector,
    active_strategies: List[str],  # ["rsi_reversal", "macd_crossover", ...]
    on_signal: Callable,           # TradingSignal 수신 콜백
)
```

**지원 전략** (`strategies/`):
| 전략명 | 클래스 | 파일 |
|--------|--------|------|
| `rsi_reversal` | RSIStrategy | strategies/rsi_strategy.py |
| `macd_crossover` | MACDStrategy | strategies/macd_strategy.py |
| `bollinger_bands` | BollingerStrategy | strategies/bollinger_strategy.py |

**전략 합산 로직**:
- 60% 이상 전략이 BUY → BUY 신호
- 60% 이상 전략이 SELL → SELL 신호
- 그 외 → HOLD (전달하지 않음)

**주요 메서드**:
- `on_market_signal(signal)`: MarketSignal 수신
- `update_strategy_params(name, params)`: 파라미터 업데이트
- `toggle_strategy(name, enabled)`: 전략 ON/OFF

---

### RiskManagerAgent (`agents/risk_manager.py`)

**역할**: 리스크 평가 및 포지션 크기 결정

**생성자 파라미터**:
```python
RiskManagerAgent(
    on_approve: Callable,             # ApprovedOrder 콜백
    max_position_size_pct: float,     # 기본: 5.0%
    max_open_positions: int,          # 기본: 5
    daily_loss_limit_pct: float,      # 기본: 3.0%
)
```

**리스크 체크 순서**:
1. 신뢰도 ≥ 50%
2. 최대 포지션 수 미달
3. 동일 심볼 중복 포지션 없음
4. 일일 손실 한도 미초과
5. 잔고 ≥ $10

**포지션 크기 계산**:
- 기본: `max_position_size_pct × confidence_multiplier`
- `confidence_multiplier`: 신뢰도 0.5~1.0 → 0.3~1.0 배율

**출력 (`ApprovedOrder`)**:
```python
@dataclass
class ApprovedOrder:
    trading_signal: TradingSignal
    symbol: str
    side: str          # buy | sell
    amount: float      # 수량
    order_type: str    # market | limit
    price: Optional[float]
    stop_loss: float
    take_profit: float
    position_size_pct: float
```

---

### ExecutionAgent (`agents/execution_agent.py`)

**역할**: 실제 주문 실행 및 손절/익절 모니터링

**생성자 파라미터**:
```python
ExecutionAgent(
    exchange: ExchangeConnector,
    on_trade_result: Callable,       # TradeResult 콜백
    on_position_update: Callable,    # 포지션 업데이트 콜백
)
```

**주요 메서드**:
- `execute_order(order)`: 주문 실행
- `close_all_positions()`: 전체 청산 (긴급)
- `_check_stop_loss_take_profit()`: 10초마다 체크 (run_cycle)

**주문 흐름**:
```
ApprovedOrder → create_market_order → TradeResult
                                    → active_positions 업데이트
                                    → on_trade_result 콜백
```

---

### PortfolioAgent (`agents/portfolio_agent.py`)

**역할**: 포트폴리오 상태 추적 및 리포트

**생성자 파라미터**:
```python
PortfolioAgent(
    exchange: ExchangeConnector,
    on_update: Callable,    # PortfolioState WebSocket 콜백
    initial_balance: float, # 기본: 10000 USDT
)
```

**포트폴리오 상태 (`PortfolioState`)**:
```python
@dataclass
class PortfolioState:
    total_value_usd: float     # 총 자산
    cash_usd: float            # 현금
    positions: Dict[str, dict] # 보유 포지션
    pnl_today: float           # 일일 손익
    pnl_total: float           # 총 손익
    total_trades: int
    winning_trades: int
    losing_trades: int
    # 계산 속성:
    # win_rate, total_return_pct
```

---

## 전략 상세

### RSIStrategy (`strategies/rsi_strategy.py`)
- **신호**: RSI < oversold → BUY, RSI > overbought → SELL
- **기본 파라미터**: period=14, oversold=30, overbought=70

### MACDStrategy (`strategies/macd_strategy.py`)
- **신호**: MACD 골든크로스 → BUY, 데드크로스 → SELL
- **기본 파라미터**: fast=12, slow=26, signal=9

### BollingerStrategy (`strategies/bollinger_strategy.py`)
- **신호**: 하단 밴드 이탈 → BUY, 상단 밴드 이탈 → SELL
- **기본 파라미터**: period=20, std_dev=2.0

---

## API 라우터

| 라우터 | 파일 | 접두사 |
|--------|------|--------|
| portfolio | routers/portfolio.py | /api/portfolio |
| trades | routers/trades.py | /api/trades |
| agents | routers/agents.py | /api/agents |
| settings | routers/settings.py | /api/settings |

## WebSocket 채널

| 채널 | 경로 | 데이터 |
|------|------|--------|
| portfolio | /ws/portfolio | PortfolioState |
| agents | /ws/agents | AgentLog |
| trades | /ws/trades | TradeResult |
| market | /ws/market | MarketSignal |

---

*최종 업데이트: 2026-03-08*  
*버전: 1.0.0*
