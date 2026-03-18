# PRD: 바이낸스 종목 기반 연구·백테스트·실매매 파이프라인

> **버전**: 1.0.0  
> **작성일**: 2026-03-18  
> **상태**: 기획 확정 (구현 단계별 진행)  
> **관련**: `crypto-auto-trading.md`, `system-trading.md`, 기존 5 에이전트 파이프라인

---

## 1. 배경 및 목적

### 1.1 왜 “거대한 자동매매 엔진”이 아닌가?

한 번에 “완성형 자동매매 엔진”을 만들면 범위가 커져 검증이 어렵다.  
**바이낸스 상장 종목(USDT 마진 현물/선물 등)** 을 전제로, 아래 **5개 레이어만 분리**해 단계적으로 구축한다.

- 데이터는 **단일 OHLCV 스키마**로 통일
- 판단은 **주문 전 “시그널 로그”** 로만 기록 (전략/LLM/룰 동일 인터페이스)
- 체결은 **시뮬레이터**에서 비용·지연을 반영 후 평가·검증

### 1.2 제품 목표

| 목표 | 설명 |
|------|------|
| **재현성** | 동일 입력 → 동일 시그널/시뮬 결과 (가능한 범위 내) |
| **비교 가능성** | 룰·지표·에이전트(LLM) 전략을 동일 `Signal` 스키마로 비교 |
| **현실 근접** | 수수료·슬리피지·스프레드·체결 지연을 백테스트/페이퍼에 반영 |
| **과최적화 방지** | OOS, walk-forward, 민감도, 국면·수수료 스트레스를 “검증 레이어”로 의무화 |
| **실매매 연결** | 검증 통과 후에만 기존 `ExecutionAgent` + Binance 실계좌(옵션)로 연결 |

### 1.3 범위 (MVP → 확장)

- **MVP**: 타임프레임 **일봉 또는 5분봉 중 1개** 고정, **종목 1~5개**, 수수료·슬리피지 반영, 진입/청산 규칙 명시, **결과 리포트 + 거래/시그널 CSV** 자동 저장.
- **확장**: `vectorbt` 대량 파라미터 스윕, walk-forward 자동화, 다종목·다타임프레임, 실거래 킬스위치.

---

## 2. 사용자 스토리

| ID | 역할 | 스토리 |
|----|------|--------|
| US-B01 | 운영자 | 바이낸스에서 선택한 심볼들의 OHLCV를 가져와 표준 포맷으로 저장·조회하고 싶다. |
| US-B02 | 전략가 | BUY/SELL/HOLD + size + reason 형태의 시그널이 시간순 로그(CSV/DB)로 남기를 원한다. |
| US-B03 | 운영자 | 백테스트 시 슬리피지·수수료·스프레드·체결 지연을 파라미터로 조절하고 싶다. |
| US-B04 | 운영자 | 누적수익률, MDD, 승률, 손익비, Sharpe, 거래횟수, 평균보유시간이 자동 리포트로 나오길 원한다. |
| US-B05 | 운영자 | In-sample / Out-of-sample, walk-forward, 파라미터 민감도, 국면별·수수료 스트레스 결과를 한눈에 보고 싶다. |
| US-B06 | 운영자 | `backtesting.py`로 1종 전략을 빠르게 검증한 뒤, 통과한 것만 페이퍼/실매매 파이프라인에 올리고 싶다. |

---

## 3. 설계 원칙 (반드시 지킬 것)

### 3.1 데이터 누수 방지

- 과거 시점 **t** 에서 의사결정 시 **t 이후 캔들 정보**를 절대 입력에 포함하지 않는다.
- **종가 기준 신호**인 경우, 동일 바의 종가에 즉시 체결한 것으로 계산하지 않는다 (다음 바 시가·지정 규칙 등 명시).

### 3.2 시그널 우선 (백테스트 툴보다 추상화가 먼저)

에이전트/전략 출력은 **즉시 주문 API로 보내지 않고**, 먼저 아래 형태의 **시그널 로그**로 통일한다.  
이로써 LLM / 룰 / 지표 전략을 **동일 인터페이스**로 백테스트·실매매 전 단계에서 비교한다.

### 3.3 LLM(에이전트) 사용 시 추가 규칙

| 항목 | 요구 |
|------|------|
| 입력 | **현재 시점까지** 데이터만 프롬프트에 포함 |
| 출력 | 자유 문장 금지 → **JSON 스키마 강제** (action, size, reason, 선택적 confidence 등) |
| 재현성 | temperature 낮추거나 고정, 가능하면 seed 고정 |
| 감사 | 의사결정 로그 저장으로 “왜 샀는지” 역추적 |

### 3.4 흔한 실패 패턴 (명시적 금지)

- 백테스트에 **수수료 미반영**
- 종가 신호인데 **같은 종가에 체결** 처리
- In-sample에만 맞춘 **파라미터 과최적화**
- **상장폐지·거래정지·극저유동성** 종목 무시
- 수백 번 실험 후 **최고 결과만 cherry-picking**하여 실매매 적용

---

## 4. 파이프라인 (논리 흐름)

```
market_data → feature_engineering → agent_signal (로그)
            → execution_simulator → portfolio_tracker
            → metrics_report → validation_layer (OOS / WF / 민감도 / 국면 / 수수료 스트레스)
```

실매매(또는 페이퍼) 연결 시:

- `execution_simulator` 대신 **실행 브리지**: 검증된 시그널만 `RiskManager` → `ExecutionAgent` → Binance.

---

## 5. 레이어별 명세

### 5.1 데이터 레이어 (Data)

**목적**: OHLCV를 **하나의 표준 포맷**으로 통일. 대부분 백테스트 프레임워크가 전제로 하는 구조.

**최소 컬럼 (스키마)**

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `datetime` | UTC, 정렬 가능 | 캔들 시작 또는 종료 시각 (프로젝트 내 **한 규칙으로 고정**하고 문서화) |
| `open` | float | 시가 |
| `high` | float | 고가 |
| `low` | float | 저가 |
| `close` | float | 종가 |
| `volume` | float | 거래량 (기준: quote 또는 base **한 가지로 통일**) |

**데이터 소스**

- **Binance** (ccxt 또는 기존 `exchange/connector`): `fetch_ohlcv`, 상장 심볼 목록(`load_markets`) 기반.
- 캐시: 로컬 SQLite/Parquet/CSV (재현성·속도).

**비기능**

- 결측·중복·타임존 일관성 검증.
- (선택) 거래정지·유동성 필터: 최소 24h 거래대금, 최소 캔들 수 등.

**참고 툴**

- `backtesting.py`: OHLC + Strategy 클래스 구조, `commission` 등 비용 변수 지원 ([kernc.github.io/backtesting.py](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html)).

---

### 5.2 시그널 레이어 (Signal)

**목적**: 주문 이전 단계의 **판단 기록**. 모든 전략 타입의 공통 계약.

**시그널 레코드 (최소 필드)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `timestamp` | datetime | 신호 생성 시각 (의사결정 시점) |
| `symbol` | str | 예: `BTC/USDT` |
| `timeframe` | str | 예: `1d`, `5m` |
| `action` | enum | `buy` \| `sell` \| `hold` |
| `size` | float | 비중 또는 수량 (단위 정책 문서화: 예: 계좌 대비 비율 0~1) |
| `reason` | str | 짧은 근거 (룰 설명, 지표 스냅샷 요약, LLM은 JSON 내 요약 필드) |
| `strategy_id` | str | 예: `rsi_reversal`, `agent_llm_v1` |
| `run_id` | str | 동일 실험 배치 식별 (재현성) |

**저장**

- CSV + (선택) DB 테이블 `signal_log`.

**OpenClaw 연계**

- 기존 `TradingSignal` / 에이전트 출력을 이 스키마로 **매핑**하거나, 백테스트 루프에서 에이전트를 호출해 동일 스키마로 적재.

---

### 5.3 실행 시뮬레이터 (Execution Simulator)

**목적**: “좋은 진입 신호”가 아니라 **실제 체결 가정**에 가깝게 PnL을 만든다.

**모델링 파라미터 (최소)**

| 파라미터 | 설명 |
|----------|------|
| `commission` | 왕복 또는 단방향 % (바이낸스 VIP/메이커·테이커 구분 가능) |
| `slippage` | 고정 bps 또는 체결가 대비 비율 |
| `spread` | 중간가 대비 매수/매도 체결가 오프셋 (간이 모델 허용) |
| `execution_delay_bars` | 신호 발생 후 N바 뒤 체결 등 |
| `fill_rule` | 예: 다음 바 시가 체결, limit 미체결 규칙 (MVP는 시장가 단순 모델 가능) |

**참고**

- Zipline 계열: 이벤트 기반, 슬리피지·거래비용·주문 지연 강조 ([zipline tutorial](https://zipline.ml4trading.io/beginner-tutorial)).

---

### 5.4 평가 레이어 (Evaluation / Metrics)

**목적**: 실험 결과를 **숫자로 고정**해 비교 가능하게 한다.

**자동 산출 지표 (필수)**

| 지표 | 설명 |
|------|------|
| 누적 수익률 | 기간 전체 |
| MDD | 최대 낙폭 |
| 승률 | 거래 단위 |
| 손익비 | 평균 이익 / 평균 손실 (정의 문서화) |
| Sharpe | 무위험금리는 0 또는 설정값, 연율화 규칙 고정 |
| 거래 횟수 | |
| 평균 보유 시간 | 바 수 또는 시간 |

**산출물**

- JSON/YAML 리포트 + 요약 CSV.
- (선택) `vectorbt` Portfolio 유사 구조로 현금·포지션·드로우다운 시계열 저장.

**참고**

- vectorbt: Portfolio 기반 통계 ([vectorbt Portfolio base](https://vectorbt.dev/api/portfolio/base/)).

---

### 5.5 검증 레이어 (Validation)

**목적**: 단일 기간 수익률만으로 실매매 결정하지 않는다.

| 검증 항목 | 내용 |
|-----------|------|
| In-sample / Out-of-sample | 학습·튜닝 구간과 완전 분리 구간 성능 |
| Walk-forward | 구간을 앞으로 밀며 재튜닝/재검증 |
| 파라미터 민감도 | 핵심 파라미터 ±x% 변동 시 성능 붕괴 여부 |
| 시장 국면별 | 고변동/저변동, 상승/하락 레짐별 (단순 분할이라도) |
| 수수료 스트레스 | 기준 수수료의 1.5배·2배에서도 전략 생존 여부 |

**합격 기준 (예시 — 구현 시 수치는 설정으로)**

- OOS에서 Sharpe > 0 또는 MDD 한도 이내 등 **팀이 정한 하한선**.
- Walk-forward에서 과반 구간 양수 등.

---

## 6. 기술 스택 권장 (단계별)

실무적으로 아래 순서를 권장한다.

| 단계 | 도구 | 용도 |
|------|------|------|
| 1 | **pandas** + **backtesting.py** | 1종 전략 빠른 검증, `Backtest.run()` / `optimize()` 구조 명확 |
| 2 | **vectorbt** | 대량 파라미터 스윕, 수천 조합 벡터화 실험 ([vectorbt](https://vectorbt.dev/)) |
| 3 | 페이퍼 시뮬레이터 | 통과 전략만 기존 OpenClaw 실행 파이프와 동일 시그널 형식으로 연결 |
| 4 | 실거래 전 | 체결 지연·슬리피지 **보수적** 재반영, 소액·킬스위치 |

**실거래에 가까운 대안 (후속)**

- **backtrader**: 전략/지표/애널라이저 중심 ([backtrader](https://www.backtrader.com/docu/)).
- **zipline-reloaded**: 이벤트 기반, 캘린더·번들로 재현성 ([Zipline docs](https://zipline.ml4trading.io/beginner-tutorial)).

OpenClaw 백엔드는 **Python**이므로 위 라이브러리는 `backend` 하위 모듈(예: `backend/research/`) 또는 별도 패키지로 의존성 분리 권장.

---

## 7. 현실적인 MVP 체크리스트

- [ ] 타임프레임 1개 (일봉 **또는** 5분봉)
- [ ] 바이낸스 심볼 1~5개 (USDT 마진 현물 등 명시)
- [ ] 표준 OHLCV 적재 + 결측 처리
- [ ] 시그널 로그 (buy/sell/hold, size, reason) CSV
- [ ] 시뮬레이터: 수수료 + 슬리피지 (스프레드·지연은 MVP에서 최소 1개 이상)
- [ ] 메트릭 리포트 자동 저장
- [ ] 거래 로그 CSV (진입/청산, 가격, 수량, 수수료)
- [ ] OOS 1회 이상 또는 walk-forward 1회 이상 (자동 스크립트)

---

## 8. API / 모듈 초안 (백엔드)

구현 시 세분화 가능. 초기에는 **CLI + 파일 출력**만으로도 충분.

| 엔드포인트/모듈 | 메서드 | 설명 |
|-----------------|--------|------|
| `/api/research/symbols` | GET | Binance USDT 현물(또는 설정 마켓) 상장 심볼 필터 목록 |
| `/api/research/ohlcv` | GET | 심볼·타임프레임·기간 → 표준 OHLCV (캐시 우선) |
| `/api/research/backtest` | POST | 시그널 생성 방식 + 시뮬 파라미터 → 메트릭 + CSV 경로/다운로드 |
| `/api/research/validate` | POST | OOS 구간·WF 설정 → 검증 리포트 |

환경변수: 기존 `BINANCE_API_KEY` 등 재사용; 연구 전용 `RESEARCH_OUTPUT_DIR` 등 추가 시 `.env.example` 반영.

---

## 9. 프론트엔드 (선택 · Phase 2)

- MVP는 **리포트 파일 + API 다운로드**로 시작.
- 이후: 시그널 타임라인 차트, 국면별 성과 테이블, walk-forward 요약 대시보드.

---

## 10. 리스크 및 안전

- 실매매는 **명시적 플래그** (`LIVE_TRADING_ENABLED=false` 기본).
- 일일 손실 한도·최대 포지션은 기존 `RiskManagerAgent`와 동일 계열 규칙 유지.
- LLM 전략은 **소액·페이퍼 기간** 의무.

---

## 11. 성공 지표

- 동일 `run_id`로 시그널 CSV + 거래 CSV + 메트릭 JSON 재실행 시 **결과 일치** (부동소수 허용 오차 내).
- MVP 종료 시: 최소 1개 전략에 대해 **OOS 또는 WF 1회** 자동 리포트 생성.

---

## 12. 다음 작업 (구현 순서 제안)

1. 데이터 레이어: Binance OHLCV → 표준 DataFrame/Parquet + 단위 테스트 (누수 없음).
2. 시그널 레이어: 1개 룰 전략 → 시그널 CSV 스키마 고정.
3. `backtesting.py` 또는 자체 루프로 실행 시뮬레이터 + 메트릭.
4. OOS 분할 스크립트 1개.
5. 페이퍼: 시그널을 기존 파이프에 주입하는 어댑터.
6. (선택) vectorbt 파라미터 스윕 스크립트.

---

## 13. 문서 참고 링크

- [backtesting.py API](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html)
- [Zipline beginner tutorial](https://zipline.ml4trading.io/beginner-tutorial)
- [vectorbt Portfolio](https://vectorbt.dev/api/portfolio/base/)
- [vectorbt 시작](https://vectorbt.dev/)
- [backtrader 문서](https://www.backtrader.com/docu/)

---

*본 PRD는 “바이낸스 종목 기반 실매매 전 연구·검증 파이프라인”의 범위를 정의한다. 구현 완료 시 `docs/handoff/handoff.md` 및 `backend/agents.md`에 연구 모듈 경로를 반영한다.*
