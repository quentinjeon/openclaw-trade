# PRD: 시스템 트레이딩 (System Trading)

> **버전**: 1.0.0  
> **작성일**: 2026-03-09  
> **상태**: 개발 중  
> **작성 관점**: 30년 주식/파생/크립토 트레이딩 도구 개발 경험 기반

---

## 1. 배경 및 목적

### 왜 시스템 트레이딩인가?

30년간 HTS(홈트레이딩시스템)를 개발해온 경험에서 가장 명확하게 배운 것은:  
**"감정 없는 룰 기반 트레이딩이 장기적으로 살아남는다"** 는 사실이다.

키움증권 영웅문, 미래에셋 MTS, TradingView의 Pine Script, NinjaTrader의 Strategy Builder까지 —  
이 모든 도구의 공통점은 **"조건식"** 이다. 트레이더가 자신의 매매 철학을 규칙으로 정의하고,  
시스템이 그 규칙을 감정 없이 실행한다.

기존 OpenClaw의 에이전트 파이프라인은 강력하지만, 고급 사용자가 자신만의 조건을 직접 만들 수 없다.  
시스템 트레이딩 모듈은 이 한계를 극복한다.

### 핵심 가치
1. **규칙의 명시화** — 머릿속의 막연한 매매 기준을 코드로 명문화
2. **감정 배제** — "아직 오를 것 같은데..."라는 인간의 본능을 차단
3. **자연어 접근성** — 코딩 없이 자연어(한국어)로 조건 작성
4. **즉시 시각화** — 차트에서 과거 어느 시점에 사야 했는지 즉시 확인
5. **반복 가능성** — 동일한 조건을 매일, 매시간 기계적으로 적용

---

## 2. 목표 사용자

### Primary: 룰 기반 트레이더
- 기술적 분석을 공부했고, 자신만의 매매 기준이 있다
- "RSI 30 이하 + 거래량 급증이면 매수"처럼 언어로 설명할 수 있다
- 코딩은 못하지만, 논리적 사고는 가능하다
- HTS 조건검색 기능을 사용해본 경험이 있다

### Secondary: 자동화를 원하는 초보 트레이더
- 유명 전략(RSI 역추세, MACD 크로스 등)을 따라 하고 싶다
- 템플릿에서 시작해서 파라미터만 조정하고 싶다
- 차트에서 신호가 실제로 어떻게 나오는지 먼저 확인하고 싶다

---

## 3. 핵심 개념 정의

### 3.1 조건식 (Condition Set)

```
조건식 = {
  이름: "내 BTC 매수전략 v3",
  대상 심볼: BTC/USDT,
  타임프레임: 1시간,
  매수 조건 (AND): [
    RSI(14) < 35,
    MACD 히스토그램 > 0 (골든크로스 발생),
    거래량 > 20일 평균 거래량 × 1.5
  ],
  매도 조건 (OR): [
    RSI(14) > 70,
    수익률 > +5%,
    손실률 > -2%
  ]
}
```

**핵심 설계 원칙**:
- **매수 조건**: 기본적으로 AND 연산 (모든 조건 충족 시 매수)
- **매도 조건**: 기본적으로 OR 연산 (하나라도 충족 시 매도)
- 각 조건 그룹 내에서 AND/OR 전환 가능
- 최대 10개 조건 / 조건식당

### 3.2 조건 노드 구조 (Condition Node)

```
단일 조건 = {
  지표 A: [지표명, 파라미터],  # 예: RSI(14), MA(20), PRICE
  연산자: <, >, <=, >=, ==, crosses_above, crosses_below,
  지표 B 또는 상수값: [지표명 | 숫자]
}
```

**크로스 연산자** (비교 대상이 다른 지표일 때):
- `crosses_above`: A가 B를 아래에서 위로 돌파
- `crosses_below`: A가 B를 위에서 아래로 돌파

예시:
- `MACD crosses_above MACD_SIGNAL` → 골든크로스
- `MA(20) crosses_above MA(50)` → 골든크로스
- `CLOSE > BB_UPPER` → 볼린저 밴드 상단 돌파

### 3.3 지원 지표 목록

#### 가격 지표
| 지표 ID | 설명 | 파라미터 |
|---------|------|---------|
| `CLOSE` | 종가 | - |
| `OPEN` | 시가 | - |
| `HIGH` | 고가 | - |
| `LOW` | 저가 | - |
| `VOLUME` | 거래량 | - |

#### 이동평균
| 지표 ID | 설명 | 파라미터 |
|---------|------|---------|
| `MA` | 단순이동평균 (SMA) | period(5~200) |
| `EMA` | 지수이동평균 | period(5~200) |
| `VWMA` | 거래량 가중이동평균 | period(5~50) |

#### 오실레이터
| 지표 ID | 설명 | 파라미터 |
|---------|------|---------|
| `RSI` | 상대강도지수 | period(2~50, 기본14) |
| `STOCH_K` | 스토캐스틱 %K | k_period, d_period |
| `STOCH_D` | 스토캐스틱 %D | k_period, d_period |
| `CCI` | 상품채널지수 | period(14~50) |

#### 추세/모멘텀
| 지표 ID | 설명 | 파라미터 |
|---------|------|---------|
| `MACD` | MACD 라인 | fast, slow, signal |
| `MACD_SIGNAL` | MACD 시그널 라인 | fast, slow, signal |
| `MACD_HIST` | MACD 히스토그램 | fast, slow, signal |
| `ADX` | 평균방향지수 | period(14) |

#### 변동성
| 지표 ID | 설명 | 파라미터 |
|---------|------|---------|
| `BB_UPPER` | 볼린저밴드 상단 | period, std_dev |
| `BB_MIDDLE` | 볼린저밴드 중간 | period |
| `BB_LOWER` | 볼린저밴드 하단 | period, std_dev |
| `BB_WIDTH` | 볼린저밴드 폭 (%) | period, std_dev |
| `ATR` | 평균진폭범위 | period(14) |

#### 파생 지표
| 지표 ID | 설명 | 파라미터 |
|---------|------|---------|
| `VOLUME_RATIO` | 거래량/MA거래량 비율 | period(20) |
| `PRICE_CHANGE` | n봉 전 대비 변화율(%) | period(1~20) |
| `CANDLE_BODY` | 캔들 몸통 크기(%) | - |
| `ABOVE_MA` | 현재가 > MA 여부 (0/1) | period |

### 3.4 Text-to-Rule 엔진 (자연어 → 조건식)

HTS 30년 경험에서 배운 것: 트레이더들은 자신의 전략을 **말로** 설명한다.  
"RSI 30 이하에서 거래량이 터지면 산다"는 말을 시스템이 이해해야 한다.

#### 파싱 전략 (2-Layer)

**Layer 1: 패턴 매칭** (빠르고 항상 동작)
자주 쓰이는 표현을 정규식으로 매핑:

```
"RSI가 [숫자] 이하" → RSI(14) <= [숫자]
"RSI가 [숫자] 아래" → RSI(14) < [숫자]  
"거래량이 평균의 [숫자]배 이상" → VOLUME_RATIO(20) >= [숫자]
"MACD 골든크로스" → MACD crosses_above MACD_SIGNAL
"볼린저 하단 이탈" → CLOSE < BB_LOWER
"이평선 돌파" (MA20) → CLOSE crosses_above MA(20)
"[숫자]일 이동평균 위" → CLOSE > MA([숫자])
```

**Layer 2: LLM 파싱** (OPENAI_API_KEY 설정 시)
패턴 매칭 실패 시 GPT를 이용해 조건 JSON 생성.  
Prompt에 지표 목록과 JSON 스키마를 포함시켜 structured output 요청.

#### 자연어 입력 예시

```
입력: "RSI 14기준으로 30 이하고 거래량이 20일 평균보다 1.5배 넘으면 매수"

출력:
{
  "operator": "AND",
  "conditions": [
    {"indicator_a": "RSI", "params_a": {"period": 14}, "op": "<=", "value_b": 30},
    {"indicator_a": "VOLUME_RATIO", "params_a": {"period": 20}, "op": ">=", "value_b": 1.5}
  ]
}
```

---

## 4. 화면 설계

### 4.1 레이아웃: `/system-trading`

```
┌──────────────────────────────────────────────────────────────────────┐
│ SIDEBAR │              시스템 트레이딩                                │
│         ├──────────────────────────────────────────────────────────── │
│         │ [내 조건식 목록]     [+ 새 조건식]      BTC/USDT ▼  1h ▼  │
│         ├──────────────────────┬───────────────────────────────────── │
│         │                     │  ┌─ 조건식 편집 패널 ─────────────┐ │
│         │  캔들 차트           │  │  조건식명: [내 BTC 전략 v1  ]  │ │
│         │  + Buy 마커 (▲)     │  │                                │ │
│         │  + Sell 마커 (▼)    │  │  [매수 조건]────────────────── │ │
│         │                     │  │  AND ▼                         │ │
│         │  [백테스트 결과 바]  │  │  ┌──────────────────────────┐ │ │
│         │  승률: 64%          │  │  │ RSI(14) <= 30      [×]  │ │ │
│         │  평균수익: +3.2%    │  │  │ VOLUME_RATIO >= 1.5 [×] │ │ │
│         │  최대낙폭: -8.1%    │  │  └──────────────────────────┘ │ │
│         │                     │  │  [+ 조건 추가]                 │ │
│         │                     │  │                                │ │
│         │                     │  │  🤖 AI 조건 입력              │ │
│         │                     │  │  ┌──────────────────────────┐ │ │
│         │                     │  │  │ "RSI 30 이하이고 거래량  │ │ │
│         │                     │  │  │  평균의 1.5배 이상"      │ │ │
│         │                     │  │  └──────────────────────────┘ │ │
│         │                     │  │  [조건 생성]                   │ │
│         │                     │  │                                │ │
│         │                     │  │  [매도 조건]────────────────── │ │
│         │                     │  │  OR ▼                          │ │
│         │                     │  │  ┌──────────────────────────┐ │ │
│         │                     │  │  │ RSI(14) >= 70      [×]  │ │ │
│         │                     │  │  │ PRICE_CHANGE >= 5   [×] │ │ │
│         │                     │  │  └──────────────────────────┘ │ │
│         │                     │  │  [+ 조건 추가]                 │ │
│         │                     │  │                                │ │
│         │                     │  │  [💾 저장]  [▶ 백테스트]     │ │
│         │                     │  └────────────────────────────────┘ │
│         └──────────────────────┴───────────────────────────────────── │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 차트 신호 표시

TradingView 스타일 마커:
- **매수 신호 (▲)**: 캔들 하단 초록색 삼각형 + "B" 텍스트
- **매도 신호 (▼)**: 캔들 상단 빨간색 삼각형 + "S" 텍스트
- 마커 클릭 시 툴팁: 발동된 조건들 표시

### 4.3 백테스트 결과 패널 (차트 하단)

```
┌──────────────────────────────────────────────────────────────┐
│ 백테스트 결과  BTC/USDT | 1h | 최근 300봉 (약 12.5일)         │
│ 총 거래: 7건 │ 승률: 4/7 (57.1%) │ 평균수익: +2.8%           │
│ 최고수익: +8.3% │ 최대손실: -3.1% │ 최대낙폭: -8.7%          │
└──────────────────────────────────────────────────────────────┘
```

### 4.4 Text-to-Rule 대화창

```
┌─ 🤖 AI 조건 만들기 ──────────────────────────────────────────┐
│                                                              │
│  💬 자연어로 매수 조건을 설명해주세요                         │
│                                                              │
│  [예시 템플릿]                                               │
│  • RSI 역추세: "RSI 30 이하에서 반등 시 매수"               │
│  • 골든크로스: "20일선이 50일선을 상향 돌파"                │
│  • 볼린저 반등: "볼린저 하단 이탈 후 종가가 다시 올라오면"  │
│  • 거래량 급증: "거래량이 20일 평균의 2배 이상"             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ RSI가 30 이하이고 MACD 골든크로스가 발생하면 매수    │   │
│  └──────────────────────────────────────────────────────┘   │
│                              [조건 생성 →]                   │
│                                                              │
│  ✅ 생성된 조건 미리보기:                                    │
│  • RSI(14) ≤ 30                                             │
│  • MACD crosses_above MACD_SIGNAL                           │
│  [매수 조건에 추가] [다시 입력]                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. API 명세

### 5.1 조건식 CRUD

```
GET    /api/system/conditions              조건식 목록 조회
POST   /api/system/conditions              조건식 생성
GET    /api/system/conditions/{id}         조건식 단건 조회
PUT    /api/system/conditions/{id}         조건식 수정
DELETE /api/system/conditions/{id}         조건식 삭제
```

### 5.2 Text-to-Rule

```
POST /api/system/text-to-rule
  Request: { "text": "RSI 30 이하이고 거래량 급증", "side": "buy" }
  Response: {
    "success": true,
    "conditions": [...],
    "explanation": "RSI(14)가 30 이하이고 거래량이 20일 평균의 1.5배 이상일 때",
    "method": "pattern" | "llm"
  }
```

### 5.3 백테스트/신호 조회

```
POST /api/system/backtest
  Request: {
    "condition_id": 1,           또는
    "condition_set": {...},       # 미저장 조건식 직접 전달
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "limit": 300                  # 캔들 수 (최대 1000)
  }
  Response: {
    "signals": [
      {"time": 1709900000, "type": "BUY", "price": 66200.0, "triggered_conditions": ["RSI=28.3", "VOLUME_RATIO=1.8"]},
      {"time": 1709950000, "type": "SELL", "price": 68100.0, "triggered_conditions": ["RSI=72.1"]}
    ],
    "stats": {
      "total_trades": 7,
      "winning_trades": 4,
      "win_rate": 57.1,
      "avg_return_pct": 2.8,
      "max_return_pct": 8.3,
      "max_loss_pct": -3.1,
      "max_drawdown_pct": -8.7,
      "total_return_pct": 15.2
    },
    "candle_count": 300
  }
```

### 5.4 실시간 현재 조건 체크

```
POST /api/system/check-now
  Request: { "condition_id": 1, "symbol": "BTC/USDT" }
  Response: {
    "triggered": true,
    "side": "BUY",
    "current_values": {"RSI": 28.3, "VOLUME_RATIO": 1.9},
    "passed_conditions": [...],
    "failed_conditions": [...]
  }
```

---

## 6. 데이터 모델

### 6.1 SystemCondition (DB 테이블)

```python
class SystemCondition(Base):
    __tablename__ = "system_conditions"

    id: int (PK)
    name: str                  # "내 BTC 매수전략 v3"
    description: str           # 사용자 설명
    symbol: str                # "BTC/USDT"
    timeframe: str             # "1h"
    
    # JSON 저장
    buy_conditions: str        # JSON: ConditionGroup
    sell_conditions: str       # JSON: ConditionGroup
    
    # 메타데이터
    is_active: bool            # 실시간 체크 활성화 여부
    created_at: datetime
    updated_at: datetime
    last_triggered_at: datetime (nullable)
    
    # 백테스트 캐시 (마지막 실행 결과)
    backtest_win_rate: float (nullable)
    backtest_trades: int (nullable)
```

### 6.2 ConditionGroup (JSON 스키마)

```json
{
  "logic": "AND",
  "conditions": [
    {
      "id": "cond_1",
      "indicator_a": "RSI",
      "params_a": {"period": 14},
      "operator": "<=",
      "type_b": "value",
      "value_b": 30
    },
    {
      "id": "cond_2",
      "indicator_a": "VOLUME_RATIO",
      "params_a": {"period": 20},
      "operator": ">=",
      "type_b": "value",
      "value_b": 1.5
    },
    {
      "id": "cond_3",
      "indicator_a": "MACD",
      "params_a": {"fast": 12, "slow": 26, "signal": 9},
      "operator": "crosses_above",
      "type_b": "indicator",
      "indicator_b": "MACD_SIGNAL",
      "params_b": {"fast": 12, "slow": 26, "signal": 9}
    }
  ]
}
```

---

## 7. 기술 아키텍처

### 7.1 조건 평가 엔진 (`backend/services/condition_evaluator.py`)

```
입력: OHLCV DataFrame (pandas) + ConditionGroup JSON
출력: 각 봉마다 조건 충족 여부 (boolean 시리즈)

처리 흐름:
1. ConditionGroup JSON 파싱
2. 각 조건의 지표 계산 (ta 라이브러리 활용)
3. 연산자 적용 (cross 연산자는 이전 봉과 비교)
4. 그룹 내 AND/OR 연산
5. 결과 시리즈 반환
```

**성능 최적화**:
- pandas 벡터 연산 사용 (봉별 루프 금지)
- 동일 지표 중복 계산 방지 (캐싱)
- 최대 1000봉으로 제한

### 7.2 백테스트 엔진 (`backend/services/backtester.py`)

```
전략 가정:
- 매수 신호 발생 봉의 다음 봉 시가에 진입
- 매도 신호 발생 봉의 다음 봉 시가에 청산
- 동시에 1개 포지션만 보유 (롱 온리)
- 수수료 0.1% 양방향

계산 항목:
- 각 트레이드별 수익률
- 총 수익률 (복리)
- 승률
- 평균 수익/손실
- 최대 낙폭 (MDD)
- Sharpe Ratio (옵션)
```

### 7.3 Text-to-Rule 파서 (`backend/services/rule_parser.py`)

```
Layer 1 패턴 매칭:
패턴 딕셔너리 → 정규식 순차 매칭 → 첫 매칭 패턴으로 조건 생성
실패 시 → Layer 2로 이동

Layer 2 LLM 파싱 (OpenAI GPT):
System Prompt: 지표 목록, JSON 스키마 설명
User Prompt: 사용자 입력 텍스트
Response Format: ConditionGroup JSON
실패 시 → 오류 메시지 반환 + 입력 수정 요청
```

### 7.4 차트 신호 렌더링

`lightweight-charts`의 `ISeriesMarker` API 사용:
```typescript
// CandleChart.tsx에 markers prop 추가
chart.createSeries("Candlestick").setMarkers([
  {
    time: 1709900000,
    position: 'belowBar',    // 캔들 아래
    color: '#22c55e',        // green-500
    shape: 'arrowUp',        // 위 화살표
    text: 'B',               // "Buy"
  },
  {
    time: 1709950000,
    position: 'aboveBar',    // 캔들 위
    color: '#ef4444',        // red-500
    shape: 'arrowDown',
    text: 'S',
  }
])
```

---

## 8. 전략 템플릿 (기본 제공)

### 8.1 RSI 역추세 전략
- 매수: RSI(14) ≤ 30 AND 거래량 > 평균의 1.3배
- 매도: RSI(14) ≥ 70 OR 수익률 ≥ +5% OR 손실률 ≤ -2%

### 8.2 MACD 골든크로스 전략
- 매수: MACD crosses_above MACD_SIGNAL AND RSI < 60
- 매도: MACD crosses_below MACD_SIGNAL OR 손실률 ≤ -3%

### 8.3 볼린저 밴드 평균회귀 전략
- 매수: CLOSE ≤ BB_LOWER AND RSI < 40
- 매도: CLOSE ≥ BB_MIDDLE OR CLOSE ≥ BB_UPPER

### 8.4 이평선 돌파 전략
- 매수: MA(20) crosses_above MA(50) AND 거래량 > 평균의 2배
- 매도: MA(20) crosses_below MA(50) OR 손실률 ≤ -3%

### 8.5 스토캐스틱 역추세 전략
- 매수: STOCH_K < 20 AND STOCH_K crosses_above STOCH_D
- 매도: STOCH_K > 80 OR STOCH_K crosses_below STOCH_D

---

## 9. UI/UX 세부 규칙

### 9.1 조건 추가 UI (3가지 방법)

**방법 1: 드롭다운 선택 (가이드드)**
```
[지표 선택 ▼] [파라미터] [연산자 ▼] [값 또는 지표 ▼]
   RSI              14      <=           30
```

**방법 2: 자연어 입력 (Text-to-Rule)**
```
[자연어 입력창] → AI 파싱 → 조건 미리보기 → [추가]
```

**방법 3: 템플릿에서 선택**
```
[RSI 역추세] [MACD 크로스] [볼린저 반등] [이평선 돌파] [스토캐스틱]
```

### 9.2 조건 편집

- 각 조건 행 우측에 **[×] 삭제** 버튼
- 드래그로 조건 순서 변경 (선택)
- AND/OR 전환 버튼
- 파라미터 클릭 시 인라인 편집

### 9.3 백테스트 실행 피드백

```
[▶ 백테스트 실행] 클릭 시:
→ 로딩 스피너 ("300봉 분석 중...")
→ 차트에 마커 렌더링
→ 하단 결과 패널 슬라이드업
→ 총 신호 수, 승률, 평균수익 표시
```

### 9.4 현재 조건 체크 상태

조건식 목록에 실시간 상태 표시:
```
[내 BTC 전략] BTC/USDT 1h  [● 미발동]  [▶ 지금 체크]
[ETH 볼린저] ETH/USDT 4h  [🔴 매수 발동!] → 알림
```

---

## 10. 단계별 구현 계획

### Phase 1: 기반 (이번 구현)
- [x] PRD 작성
- [ ] DB 모델 (`SystemCondition`)
- [ ] 조건 평가 엔진 (`condition_evaluator.py`)
- [ ] 백테스트 엔진 (`backtester.py`)
- [ ] Text-to-Rule 파서 (Layer 1: 패턴 매칭)
- [ ] REST API (`/api/system/*`)
- [ ] 프론트엔드 기본 레이아웃 (`/system-trading`)
- [ ] 차트 Buy/Sell 마커 렌더링
- [ ] 조건 CRUD UI
- [ ] 백테스트 결과 패널

### Phase 2: 고도화 (추후)
- [ ] Text-to-Rule Layer 2 (LLM, OpenAI API 연동)
- [ ] 전략 템플릿 5종 제공
- [ ] 실시간 조건 모니터링 (WebSocket 알림)
- [ ] 조건식 활성화 → 에이전트 파이프라인 연동
- [ ] 조건식 공유/내보내기 (JSON export)
- [ ] 복합 조건 그룹 (AND 안에 OR 그룹)
- [ ] 멀티 심볼 스캔 (여러 코인 동시 조건 검색)

---

## 11. 완료 기준 (Definition of Done)

- [ ] `/system-trading` 페이지 접속 가능
- [ ] 조건식 생성/저장/불러오기 동작
- [ ] 자연어 입력 → 조건 생성 동작 (패턴 매칭)
- [ ] 백테스트 실행 → 차트에 Buy/Sell 마커 표시
- [ ] 백테스트 결과 통계 표시 (승률, 평균수익, MDD)
- [ ] 템플릿 3종 이상 제공
- [ ] 현재 조건 체크 (`/api/system/check-now`) 동작
- [ ] 사이드바에 "시스템 트레이딩" 메뉴 추가

---

## 12. 설계 원칙 (30년 노하우)

> "좋은 트레이딩 도구는 트레이더의 나쁜 습관을 막아야 한다."

1. **결과보다 과정**: 백테스트 결과가 좋아도 "데이터 스누핑"을 경고해야 한다
2. **단순한 것이 강하다**: 조건이 5개를 넘어가면 과최적화 경고 표시
3. **현실적인 가정**: 슬리피지, 수수료, 유동성 고려
4. **감정 차단**: 실시간 알림 시 조건만 보여주고 "어떻게 해야 할지"는 절대 권고하지 않음
5. **기록의 중요성**: 모든 조건 변경 이력 보관 (언제 규칙을 바꿨는지가 중요)

---

*최종 업데이트: 2026-03-09*  
*버전: 1.0.0*
